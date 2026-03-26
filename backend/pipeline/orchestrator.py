import structlog
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from pipeline.state import PipelineState
from agents.intent_agent import run_intent_agent
from agents.writer_agent import run_writer_agent, fetch_rag_context
from agents.compile_agent import run_compile_agent, run_compile_agent_sandbox
from agents.fix_agent import run_fix_agent, run_fix_agent_sandbox
from agents.deploy_agent import run_deploy_agent, run_deploy_agent_sandbox
from sandbox.daml_sandbox import DamlSandbox
from tools.daml_tools import create_template, add_signatory, add_choice
from security.hybrid_auditor import run_hybrid_audit
from config import get_settings

logger = structlog.get_logger()

MAX_FIX_ATTEMPTS = 3

FALLBACK_CONTRACT = """module Main where

template SimpleContract
  with
    issuer : Party
    owner : Party
    amount : Decimal
  where
    signatory issuer
    observer owner

    ensure amount > 0.0

    choice Transfer : ContractId SimpleContract
      with
        newOwner : Party
      controller owner
      do
        create this with owner = newOwner
"""

# Global registry for per-job status callbacks so nodes can push updates
_status_callbacks: dict = {}


def _push_status(state: dict, step: str, progress: int):
    """Push an intermediate status update if a callback is registered for this job."""
    job_id = state.get("job_id")
    if job_id and job_id in _status_callbacks:
        try:
            _status_callbacks[job_id](job_id, "running", step, progress)
        except Exception:
            pass


def intent_node(state: dict) -> dict:
    logger.info("Node: intent", job_id=state.get("job_id"))
    _push_status(state, "Parsing contract intent...", 10)
    result = run_intent_agent(state["user_input"])
    if not result["success"]:
        logger.error("Intent node failed", error=result.get("error"))
        return {
            **state,
            "error_message":  result.get("error", "Intent agent failed"),
            "is_fatal_error": True,
            "current_step":   "Failed at intent analysis",
            "progress":       0,
        }
    return {
        **state,
        "structured_intent": result["structured_intent"],
        "current_step":      "Retrieving DAML patterns...",
        "progress":          20,
    }


def rag_node(state: dict) -> dict:
    logger.info("Node: RAG retrieval", job_id=state.get("job_id"))
    _push_status(state, "Retrieving DAML patterns...", 25)
    try:
        context = fetch_rag_context(state["structured_intent"])
        return {
            **state,
            "rag_context":  context,
            "current_step": "Generating DAML code...",
            "progress":     30,
        }
    except Exception as e:
        logger.warning("RAG retrieval failed, continuing without context", error=str(e))
        return {
            **state,
            "rag_context":  [],
            "current_step": "Generating DAML code...",
            "progress":     30,
        }


def generate_node(state: dict) -> dict:
    logger.info("Node: generate", job_id=state.get("job_id"))
    _push_status(state, "Generating DAML code...", 35)
    result = run_writer_agent(
        structured_intent=state["structured_intent"],
        rag_context=state.get("rag_context", []),
    )
    if not result["success"]:
        logger.error("Generate node failed", error=result.get("error"))
        return {
            **state,
            "error_message":  result.get("error", "Writer agent failed"),
            "is_fatal_error": True,
            "current_step":   "Failed at code generation",
            "progress":       0,
        }
    return {
        **state,
        "generated_code": result["daml_code"],
        "current_step":   "Compiling contract...",
        "progress":       50,
    }


def compile_node(state: dict) -> dict:
    job_id = state.get("job_id", "unknown")
    attempt = state.get("attempt_number", 0) + 1
    logger.info("Node: compile", job_id=job_id, attempt=attempt)
    _push_status(state, f"Compiling contract (attempt {attempt})...", 50)

    try:
        result = run_compile_agent(state["generated_code"], job_id)
        if result["success"]:
            _push_status(state, "Compilation successful! Deploying...", 80)
            return {
                **state,
                "compile_result":  "success",
                "compile_success": True,
                "compile_errors":  [],
                "dar_path":        result.get("dar_path", ""),
                "attempt_number":  attempt,
                "current_step":    "Deploying to Canton...",
                "progress":        80,
            }
        else:
            progress = 50 + min(attempt * 5, 15)
            return {
                **state,
                "compile_result":  result.get("raw_error", ""),
                "compile_success": False,
                "compile_errors":  result.get("errors", []),
                "dar_path":        "",
                "attempt_number":  attempt,
                "current_step":    f"Fixing errors (attempt {attempt}/{MAX_FIX_ATTEMPTS})...",
                "progress":        progress,
            }
    except Exception as e:
        logger.error("Compile node failed", error=str(e))
        return {
            **state,
            "compile_success": False,
            "compile_errors":  [{"message": str(e), "type": "unknown", "fixable": True}],
            "attempt_number":  attempt,
            "current_step":    "Compilation error",
        }


def fix_node(state: dict) -> dict:
    attempt = state.get("attempt_number", 1)
    logger.info("Node: fix", job_id=state.get("job_id"), attempt=attempt)
    _push_status(state, f"Auto-fixing errors (attempt {attempt}/{MAX_FIX_ATTEMPTS})...", 60)

    result = run_fix_agent(
        daml_code=state["generated_code"],
        compile_errors=state.get("compile_errors", []),
        attempt_number=attempt,
    )
    if not result["success"]:
        logger.warning("Fix node failed", error=result.get("error"))
        return {
            **state,
            "current_step": f"Fix attempt {attempt} failed, retrying...",
        }
    return {
        **state,
        "generated_code": result["fixed_code"],
        "current_step":   f"Recompiling after fix (attempt {attempt})...",
        "progress":       65,
    }


def fallback_node(state: dict) -> dict:
    """Replace generated code with guaranteed-compilable fallback contract."""
    logger.info("Node: fallback (using guaranteed contract)", job_id=state.get("job_id"))
    _push_status(state, "Using fallback contract template", 75)

    return {
        **state,
        "generated_code":   FALLBACK_CONTRACT,
        "attempt_number":   0,
        "compile_errors":   [],
        "compile_success":  False,
        "fallback_used":    True,
        "current_step":     "Using fallback contract template",
        "progress":         75,
    }


def audit_node(state: dict) -> dict:
    """Run enterprise security audit and compliance analysis on compiled DAML code."""
    job_id = state.get("job_id", "unknown")
    logger.info("Node: audit", job_id=job_id)
    _push_status(state, "Running security audit & compliance analysis...", 82)

    daml_code = state.get("generated_code", "")
    if not daml_code:
        logger.warning("No DAML code to audit, skipping")
        return {
            **state,
            "audit_result": None,
            "security_score": None,
            "compliance_score": None,
            "current_step": "Deploying to Canton...",
            "progress": 85,
        }

    try:
        contract_name = (
            state.get("structured_intent", {})
            .get("daml_templates_needed", ["Contract"])[0]
        )
    except (IndexError, TypeError):
        contract_name = "Contract"

    try:
        audit_result = run_hybrid_audit(
            daml_code=daml_code,
            contract_name=contract_name,
            compliance_profile="generic",
        )

        security_score = audit_result.get("combined_scores", {}).get("security_score")
        compliance_score = audit_result.get("combined_scores", {}).get("compliance_score")
        enterprise_score = audit_result.get("combined_scores", {}).get("enterprise_score")
        deploy_gate = audit_result.get("combined_scores", {}).get("deploy_gate", True)

        _push_status(
            state,
            f"Audit complete — Security: {security_score}/100, Compliance: {compliance_score}/100",
            85,
        )

        logger.info(
            "Audit node completed",
            job_id=job_id,
            security_score=security_score,
            compliance_score=compliance_score,
            enterprise_score=enterprise_score,
            deploy_gate=deploy_gate,
        )

        return {
            **state,
            "audit_result": audit_result,
            "security_score": security_score,
            "compliance_score": compliance_score,
            "enterprise_score": enterprise_score,
            "deploy_gate": deploy_gate,
            "audit_reports": audit_result.get("reports", {}),
            "current_step": "Deploying to Canton..." if deploy_gate else "Security gate failed — deploying anyway...",
            "progress": 85,
        }

    except Exception as e:
        logger.error("Audit node failed, continuing to deploy", error=str(e))
        return {
            **state,
            "audit_result": None,
            "security_score": None,
            "compliance_score": None,
            "current_step": "Audit failed, deploying to Canton...",
            "progress": 85,
        }


def deploy_node(state: dict) -> dict:
    logger.info("Node: deploy", job_id=state.get("job_id"))
    _push_status(state, "Deploying to Canton ledger...", 90)

    settings = get_settings()
    canton_url = state.get("canton_url") or settings.get_canton_url()
    canton_env = state.get("canton_environment", "sandbox")
    fallback_used = state.get("fallback_used", False)

    party_id = state.get("party_id", "")
    try:
        result = run_deploy_agent(
            dar_path=state.get("dar_path", ""),
            structured_intent=state.get("structured_intent", {}),
            canton_url=canton_url,
            canton_environment=canton_env,
            party_id=party_id,
        )

        if result["success"]:
            _push_status(state, "Contract deployed! Verifying...", 95)
            template_name = "SimpleContract" if fallback_used else result.get("template_id", "")
            return {
                **state,
                "contract_id":   result["contract_id"],
                "package_id":    result["package_id"],
                "template_id":   result.get("template_id", ""),
                "template":      template_name,
                "parties":       result.get("parties", {}),
                "explorer_link": result.get("explorer_link", ""),
                "fallback_used": fallback_used,
                "current_step":  "Contract deployed successfully!",
                "progress":      100,
            }
        else:
            return {
                **state,
                "error_message":  result.get("error", "Deployment failed"),
                "is_fatal_error": True,
                "current_step":   "Deployment failed",
                "progress":       80,
            }
    except Exception as e:
        logger.error("Deploy node failed", error=str(e))
        return {
            **state,
            "error_message":  str(e),
            "is_fatal_error": True,
            "current_step":   "Deployment failed",
        }


def error_node(state: dict) -> dict:
    logger.error("Pipeline reached error node", job_id=state.get("job_id"), error=state.get("error_message"))
    return {
        **state,
        "current_step": "Failed — max retries exceeded",
        "progress":     0,
    }


def _route_after_compile(state: dict) -> Literal["audit", "fix", "fallback"]:
    if state.get("compile_success"):
        return "audit"

    attempt = state.get("attempt_number", 0)

    # After MAX_FIX_ATTEMPTS: use fallback contract (never go to error)
    if attempt >= MAX_FIX_ATTEMPTS:
        return "fallback"

    return "fix"


def _route_after_intent(state: dict) -> Literal["rag", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "rag"


def _route_after_generate(state: dict) -> Literal["compile", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "compile"


def build_pipeline() -> CompiledStateGraph:
    graph = StateGraph(dict)

    graph.add_node("intent",   intent_node)
    graph.add_node("rag",      rag_node)
    graph.add_node("generate", generate_node)
    graph.add_node("compile",  compile_node)
    graph.add_node("fix",      fix_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("audit",    audit_node)
    graph.add_node("deploy",   deploy_node)
    graph.add_node("error",    error_node)

    graph.set_entry_point("intent")

    graph.add_conditional_edges("intent", _route_after_intent, {"rag": "rag", "error": "error"})
    graph.add_edge("rag", "generate")
    graph.add_conditional_edges("generate", _route_after_generate, {"compile": "compile", "error": "error"})
    graph.add_conditional_edges(
        "compile",
        _route_after_compile,
        {"audit": "audit", "fix": "fix", "fallback": "fallback"},
    )
    graph.add_edge("fix", "compile")
    graph.add_edge("fallback", "compile")  # recompile after fallback — guaranteed success
    graph.add_edge("audit", "deploy")
    graph.add_edge("deploy", END)
    graph.add_edge("error",  END)

    return graph.compile()


async def run_mvp_pipeline(
    job_id: str,
    user_input: str,
    canton_url: str = "http://localhost:7575",
    auth_token: str | None = None,
    max_fix_attempts: int = 3,
) -> dict:
    """
    Minimal async pipeline: English → DAML → Compile → Fix → Deploy → Contract ID.

    Uses DamlSandbox for isolated project execution.
    Returns a result dict with success, contract_id, and package_id.
    """
    logger.info("Starting MVP pipeline", job_id=job_id)

    settings = get_settings()

    # --- Step 1: Intent ---
    intent_result = run_intent_agent(user_input)
    if not intent_result["success"]:
        return {
            "success": False,
            "stage": "intent",
            "error": intent_result.get("error", "Intent agent failed"),
            "contract_id": "",
            "package_id": "",
        }

    structured_intent = intent_result["structured_intent"]
    parties = structured_intent.get("parties", ["issuer", "owner"])
    templates = structured_intent.get("daml_templates_needed", ["Main"])
    project_name = templates[0] if templates else "GinieContract"

    # MVP: cap to single template for reliable compilation
    structured_intent["daml_templates_needed"] = [project_name]
    structured_intent["suggested_choices"] = structured_intent.get("suggested_choices", [])[:4]
    logger.info("Intent parsed", project_name=project_name, parties=parties)

    # --- Step 2: Create sandbox ---
    sandbox = DamlSandbox(job_id, project_name)
    await sandbox.initialize()

    # --- Step 3: RAG + generate DAML ---
    try:
        rag_context = fetch_rag_context(structured_intent)
    except Exception:
        rag_context = []

    write_result = run_writer_agent(
        structured_intent=structured_intent,
        rag_context=rag_context,
    )
    if not write_result["success"]:
        await sandbox.cleanup()
        return {
            "success": False,
            "stage": "generate",
            "error": write_result.get("error", "Writer agent failed"),
            "contract_id": "",
            "package_id": "",
        }

    daml_code = write_result["daml_code"]
    await sandbox.files.write("daml/Main.daml", daml_code)
    logger.info("DAML code written to sandbox", project_name=project_name)

    # --- Step 4: Compile → Fix loop (max_fix_attempts) ---
    compile_result = None
    fix_attempt = 0

    for attempt in range(max_fix_attempts + 1):
        compile_result = await run_compile_agent_sandbox(sandbox, project_name)

        if compile_result["compile_success"]:
            logger.info("Compilation succeeded", attempt=attempt)
            break

        if attempt >= max_fix_attempts:
            logger.error("Max fix attempts reached", attempts=attempt)
            await sandbox.cleanup()
            return {
                "success": False,
                "stage": "compile",
                "error": f"Compilation failed after {max_fix_attempts} fix attempts",
                "compile_errors": compile_result.get("compile_errors", []),
                "contract_id": "",
                "package_id": "",
            }

        logger.info("Applying fixes", attempt=attempt, errors=len(compile_result.get("compile_errors", [])))
        fix_result = await run_fix_agent_sandbox(
            sandbox,
            compile_result.get("compile_errors", []),
            attempt=fix_attempt,
            max_attempts=max_fix_attempts,
        )

        # If targeted fixes made no changes, fall back to LLM-based fixing
        if not fix_result.get("changed", False):
            logger.info("Targeted fixes made no change, falling back to LLM fix agent")
            try:
                current_code = await sandbox.files.read("daml/Main.daml")
                llm_fix = run_fix_agent(
                    daml_code=current_code,
                    compile_errors=compile_result.get("compile_errors", []),
                    attempt_number=fix_attempt,
                )
                if llm_fix.get("success") and llm_fix.get("fixed_code"):
                    await sandbox.files.write("daml/Main.daml", llm_fix["fixed_code"])
                    logger.info("LLM fix agent applied", code_length=len(llm_fix["fixed_code"]))
            except Exception as llm_exc:
                logger.warning("LLM fix agent failed", error=str(llm_exc))

        fix_attempt += 1

    # --- Step 5: Deploy ---
    deploy_result = await run_deploy_agent_sandbox(
        sandbox=sandbox,
        project_name=project_name,
        parties=parties,
        canton_url=canton_url,
        auth_token=auth_token,
    )

    await sandbox.cleanup()

    if not deploy_result["success"]:
        return {
            "success": False,
            "stage": "deploy",
            "error": deploy_result.get("error", "Deploy failed"),
            "contract_id": "",
            "package_id": deploy_result.get("package_id", ""),
        }

    logger.info(
        "MVP pipeline complete",
        job_id=job_id,
        contract_id=deploy_result["contract_id"],
        package_id=deploy_result["package_id"],
    )

    return {
        "success": True,
        "contract_id": deploy_result["contract_id"],
        "package_id": deploy_result["package_id"],
        "parties": deploy_result.get("parties", {}),
        "template_id": deploy_result.get("template_id", ""),
        "stage": "complete",
    }


def run_pipeline(job_id: str, user_input: str, canton_environment: str = "sandbox", canton_url: str = "", status_callback=None, party_id: str = "") -> dict:
    settings = get_settings()

    initial_state = {
        "job_id":             job_id,
        "user_input":         user_input,
        "structured_intent":  {},
        "rag_context":        [],
        "generated_code":     "",
        "compile_result":     "",
        "compile_success":    False,
        "compile_errors":     [],
        "attempt_number":     0,
        "fallback_used":      False,
        "dar_path":           "",
        "contract_id":        "",
        "package_id":         "",
        "template_id":        "",
        "parties":            {},
        "explorer_link":      "",
        "error_message":      "",
        "is_fatal_error":     False,
        "current_step":       "Analyzing your contract description...",
        "progress":           10,
        "canton_environment": canton_environment,
        "canton_url":         canton_url or settings.get_canton_url(),
        "party_id":           party_id,
    }

    # Register callback so pipeline nodes can push real-time updates
    if status_callback:
        _status_callbacks[job_id] = status_callback
        status_callback(job_id, "running", "Analyzing your contract description...", 10)

    try:
        pipeline = build_pipeline()
        final_state = pipeline.invoke(initial_state)
    finally:
        # Always cleanup the callback
        _status_callbacks.pop(job_id, None)

    if final_state.get("contract_id"):
        derived_status = "complete"
    elif final_state.get("is_fatal_error") or final_state.get("error_message"):
        derived_status = "failed"
    else:
        derived_status = "complete"

    final_state["status"]     = derived_status
    final_state["daml_code"]  = final_state.get("generated_code", "")

    logger.info(
        "Pipeline completed",
        job_id=job_id,
        status=derived_status,
        attempts=final_state.get("attempt_number"),
    )

    return final_state
