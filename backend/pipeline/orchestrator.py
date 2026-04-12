import structlog
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from pipeline.state import PipelineState
from agents.intent_agent import run_intent_agent
from agents.writer_agent import run_writer_agent, fetch_rag_context
from agents.project_writer_agent import run_project_writer_agent
from agents.compile_agent import run_compile_agent, run_compile_agent_sandbox
from agents.fix_agent import run_fix_agent, run_fix_agent_sandbox
from agents.deploy_agent import run_deploy_agent, run_deploy_agent_sandbox
from agents.proposal_injector import inject_proposal_pattern
from agents.diagram_agent import parse_daml_for_diagram, generate_mermaid
from security.hybrid_auditor import run_hybrid_audit
from config import get_settings

logger = structlog.get_logger()

_COMPILED_PIPELINE: CompiledStateGraph | None = None

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


def _max_fix_attempts() -> int:
    return get_settings().max_fix_attempts


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

    daml_code = result["daml_code"]
    intent = state.get("structured_intent", {})

    # Post-processing: inject Propose-Accept pattern if needed
    if intent.get("needs_proposal"):
        parties = intent.get("parties", ["issuer", "investor"])
        initiator = parties[0] if parties else "issuer"
        acceptors = parties[1:2] if len(parties) > 1 else ["acceptor"]
        _push_status(state, "Injecting Propose-Accept pattern...", 42)
        try:
            daml_code = inject_proposal_pattern(daml_code, initiator, acceptors)
            logger.info("Propose-Accept pattern injected", initiator=initiator, acceptors=acceptors)
        except Exception as e:
            logger.warning("Proposal injection failed, continuing with core template", error=str(e))

    return {
        **state,
        "generated_code": daml_code,
        "current_step":   "Compiling contract...",
        "progress":       50,
    }


def generate_project_node(state: dict) -> dict:
    """Multi-template project generation (project_mode == True)."""
    logger.info("Node: generate_project", job_id=state.get("job_id"))
    _push_status(state, "Generating multi-template DAML project...", 35)
    result = run_project_writer_agent(
        structured_intent=state["structured_intent"],
        rag_context=state.get("rag_context", []),
    )
    if not result["success"]:
        logger.error("Project generate node failed", error=result.get("error"))
        return {
            **state,
            "error_message":  result.get("error", "Project writer agent failed"),
            "is_fatal_error": True,
            "current_step":   "Failed at project generation",
            "progress":       0,
        }

    files = result["files"]
    # Combine all files into a single code string for compile/audit/deploy
    # (compile_node writes individual files but generated_code holds the combined view)
    combined = "\n\n".join(f"-- FILE: {fname}\n{code}" for fname, code in files.items())

    intent = state.get("structured_intent", {})

    # Inject Propose-Accept on core template if needed
    if intent.get("needs_proposal"):
        parties = intent.get("parties", ["issuer", "investor"])
        initiator = parties[0] if parties else "issuer"
        acceptors = parties[1:2] if len(parties) > 1 else ["acceptor"]
        _push_status(state, "Injecting Propose-Accept pattern...", 42)
        # Find the core template file and inject proposal into it
        core_name = result.get("primary_template", "")
        core_file = f"daml/{core_name}.daml" if core_name else None
        if core_file and core_file in files:
            try:
                files[core_file] = inject_proposal_pattern(files[core_file], initiator, acceptors)
                # Rebuild combined view
                combined = "\n\n".join(f"-- FILE: {fname}\n{code}" for fname, code in files.items())
                logger.info("Propose-Accept injected into project", core_file=core_file)
            except Exception as e:
                logger.warning("Proposal injection failed in project mode", error=str(e))

    return {
        **state,
        "generated_code":   combined,
        "project_mode":     True,
        "project_files":    files,
        "daml_yaml":        result.get("daml_yaml", ""),
        "primary_template": result.get("primary_template", ""),
        "current_step":     "Compiling project...",
        "progress":         50,
    }


def diagram_node(state: dict) -> dict:
    """Generate a Mermaid contract flow diagram from the compiled DAML code."""
    job_id = state.get("job_id", "unknown")
    logger.info("Node: diagram", job_id=job_id)
    _push_status(state, "Generating contract flow diagram...", 86)

    try:
        code = state.get("project_files") or state.get("generated_code", "")
        spec = parse_daml_for_diagram(code)
        mermaid = generate_mermaid(spec)
        logger.info("Diagram generated",
                    templates=len(spec.get("templates", [])),
                    flows=len(spec.get("flows", [])))
        return {
            **state,
            "diagram_mermaid": mermaid,
            "diagram_spec":   spec,
            "current_step":   "Deploying to Canton...",
            "progress":       88,
        }
    except Exception as e:
        logger.warning("Diagram generation failed, skipping", error=str(e))
        return {
            **state,
            "diagram_mermaid": "",
            "diagram_spec":   {},
            "current_step":   "Deploying to Canton...",
            "progress":       88,
        }


def compile_node(state: dict) -> dict:
    job_id = state.get("job_id", "unknown")
    attempt = state.get("attempt_number", 0) + 1
    logger.info("Node: compile", job_id=job_id, attempt=attempt)
    _push_status(state, f"Compiling contract (attempt {attempt})...", 50)

    try:
        result = run_compile_agent(
            state["generated_code"], job_id,
            project_files=state.get("project_files"),
            daml_yaml=state.get("daml_yaml", ""),
        )
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
                "current_step":    f"Fixing errors (attempt {attempt}/{_max_fix_attempts()})...",
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
    _push_status(state, f"Auto-fixing errors (attempt {attempt}/{_max_fix_attempts()})...", 60)

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

    # Preserve original project files for the user even though we're falling back
    original_project_files = state.get("project_files", {})

    return {
        **state,
        "generated_code":           FALLBACK_CONTRACT,
        "attempt_number":           0,
        "compile_errors":           [],
        "compile_success":          False,
        "fallback_used":            True,
        "project_mode":             False,
        "project_files":            {},
        "daml_yaml":                "",
        "original_project_files":   original_project_files,
        "current_step":             "Using fallback contract template",
        "progress":                 75,
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
            "current_step": "Running security audit..." if deploy_gate else "Security gate failed — deployment will be blocked",
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

    if state.get("deploy_gate") is False:
        settings = get_settings()
        if settings.canton_environment != "sandbox":
            logger.warning("Security gate blocked deployment — contract NOT deployed", job_id=state.get("job_id"))
            _push_status(state, "Deployment blocked by security audit gate", 90)
            return {
                **state,
                "error_message":  "Security gate blocked deployment. Audit found critical vulnerabilities — fix them before deploying.",
                "is_fatal_error": True,
                "current_step":   "Blocked by security gate — not deployed",
                "progress":       90,
            }
        else:
            logger.warning("Security gate would block deployment but sandbox mode — proceeding anyway", job_id=state.get("job_id"))

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

            # Build deployment note for Propose-Accept contracts
            intent = state.get("structured_intent", {})
            deployment_note = ""
            if intent.get("needs_proposal") and not fallback_used:
                proposal_tmpl = result.get("template_id", "").rsplit(":", 1)[-1] if result.get("template_id") else ""
                if "Proposal" in proposal_tmpl or "Proposal" in template_name:
                    parties = intent.get("parties", [])
                    acceptor = parties[1] if len(parties) > 1 else "acceptor"
                    deployment_note = (
                        f"Created {proposal_tmpl or template_name} contract. "
                        f"To complete the agreement, {acceptor} must exercise the Accept choice on this contract. "
                        f"POST /v1/exercise with contractId and choice '{proposal_tmpl}_Accept'"
                    )

            return {
                **state,
                "contract_id":     result["contract_id"],
                "package_id":      result["package_id"],
                "template_id":     result.get("template_id", ""),
                "template":        template_name,
                "parties":         result.get("parties", {}),
                "explorer_link":   result.get("explorer_link", ""),
                "fallback_used":   fallback_used,
                "deployment_note": deployment_note,
                "current_step":    "Contract deployed successfully!",
                "progress":        100,
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

    if attempt >= _max_fix_attempts():
        return "fallback"

    return "fix"


def _route_after_intent(state: dict) -> Literal["rag", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "rag"


def _route_after_rag(state: dict) -> Literal["generate", "generate_project"]:
    """Route to single-template or multi-template generation."""
    if state.get("structured_intent", {}).get("project_mode"):
        return "generate_project"
    return "generate"


def _route_after_generate(state: dict) -> Literal["compile", "error"]:
    if state.get("is_fatal_error"):
        return "error"
    return "compile"


def _build_pipeline() -> CompiledStateGraph:
    graph = StateGraph(dict)

    graph.add_node("intent",           intent_node)
    graph.add_node("rag",              rag_node)
    graph.add_node("generate",         generate_node)
    graph.add_node("generate_project", generate_project_node)
    graph.add_node("compile",          compile_node)
    graph.add_node("fix",              fix_node)
    graph.add_node("fallback",         fallback_node)
    graph.add_node("audit",            audit_node)
    graph.add_node("diagram",          diagram_node)
    graph.add_node("deploy",           deploy_node)
    graph.add_node("error",            error_node)

    graph.set_entry_point("intent")

    graph.add_conditional_edges("intent", _route_after_intent, {"rag": "rag", "error": "error"})
    graph.add_conditional_edges(
        "rag",
        _route_after_rag,
        {"generate": "generate", "generate_project": "generate_project"},
    )
    graph.add_conditional_edges("generate", _route_after_generate, {"compile": "compile", "error": "error"})
    graph.add_conditional_edges("generate_project", _route_after_generate, {"compile": "compile", "error": "error"})
    graph.add_conditional_edges(
        "compile",
        _route_after_compile,
        {"audit": "audit", "fix": "fix", "fallback": "fallback"},
    )
    graph.add_edge("fix", "compile")
    graph.add_edge("fallback", "compile")  # recompile after fallback — guaranteed success
    graph.add_edge("audit", "diagram")
    graph.add_edge("diagram", "deploy")
    graph.add_edge("deploy", END)
    graph.add_edge("error",  END)

    return graph.compile()


def build_pipeline() -> CompiledStateGraph:
    global _COMPILED_PIPELINE
    if _COMPILED_PIPELINE is None:
        _COMPILED_PIPELINE = _build_pipeline()
    return _COMPILED_PIPELINE


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
        "project_mode":       False,
        "project_files":      {},
        "daml_yaml":          "",
        "diagram_mermaid":    "",
        "diagram_spec":       {},
        "deployment_note":    "",
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
