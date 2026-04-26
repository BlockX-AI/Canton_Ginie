import structlog
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from agents.intent_agent import run_intent_agent
from agents.writer_agent import run_writer_agent, fetch_rag_context
from agents.project_writer_agent import run_project_writer_agent
from pipeline.spec_synth import synthesize_spec
from agents.compile_agent import run_compile_agent
from agents.fix_agent import run_fix_agent
from agents.deploy_agent import run_deploy_agent
from agents.proposal_injector import inject_proposal_pattern
from agents.diagram_agent import parse_daml_for_diagram, generate_mermaid
from security.hybrid_auditor import run_hybrid_audit
from config import get_settings
from utils.branding import prepend_brand_header
from pipeline.events import (
    emit,
    emit_log,
    emit_stage_started,
    emit_stage_completed,
    emit_stage_failed,
    PIPELINE_STAGES,
)

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
    emit_stage_started(state, "intent", "Analyzing your contract description\u2026")
    result = run_intent_agent(state["user_input"])
    if not result["success"]:
        logger.error("Intent node failed", error=result.get("error"))
        emit_stage_failed(state, "intent", result.get("error", "Intent agent failed"))
        return {
            **state,
            "error_message":  result.get("error", "Intent agent failed"),
            "is_fatal_error": True,
            "current_step":   "Failed at intent analysis",
            "progress":       0,
        }
    intent = result["structured_intent"]
    parties = intent.get("parties", []) if isinstance(intent, dict) else []
    templates = intent.get("daml_templates_needed", []) if isinstance(intent, dict) else []
    emit_stage_completed(
        state,
        "intent",
        f"Intent parsed \u2014 {len(templates) or 1} template(s), parties: {', '.join(parties) or 'n/a'}",
        templates=list(templates),
        parties=list(parties),
        project_mode=bool(intent.get("project_mode")) if isinstance(intent, dict) else False,
    )
    return {
        **state,
        "structured_intent": intent,
        "current_step":      "Synthesising contract plan...",
        "progress":          18,
    }


def spec_synth_node(state: dict) -> dict:
    """Synthesise a structured contract spec from the user prompt + intent.

    The spec is a strict checklist (parties / fields / behaviours /
    non-behaviours / invariants / test scenarios) that the writer agent
    consumes as a constraint and the auditor will later use as a
    conformance reference. This stage is best-effort: failures here never
    block code generation \u2014 the pipeline simply falls back to the
    intent-only writer prompt.
    """
    logger.info("Node: spec_synth", job_id=state.get("job_id"))
    _push_status(state, "Synthesising contract plan...", 22)
    emit_stage_started(state, "spec", "Drafting a structured contract plan\u2026")

    spec = None
    try:
        spec = synthesize_spec(state.get("user_input", ""), state.get("structured_intent") or {})
    except Exception as e:
        logger.warning("Spec synth crashed, continuing without spec", error=str(e))
        spec = None

    if not spec:
        # Soft skip: mark the stage completed with a warning log so the
        # strip turns green (pipeline is healthy) but the user can still
        # see in the live log that the planner declined to produce a spec.
        emit_log(
            state,
            "Spec synthesis skipped \u2014 generator will use intent only",
            level="warn",
        )
        emit_stage_completed(state, "spec", "No structured plan produced (continuing)")
        return {
            **state,
            "contract_spec": None,
            "current_step":  "Retrieving DAML patterns...",
            "progress":      24,
        }

    # Push the full spec out to the live-log + event log so the frontend
    # can render the Plan panel before any code is written.
    emit(
        state,
        "spec_ready",
        f"Plan ready \u2014 {spec.get('pattern', 'generic')} ({len(spec.get('behaviours') or [])} behaviour(s), "
        f"{len(spec.get('non_behaviours') or [])} non-behaviour(s))",
        level="success",
        data={"spec": spec},
    )
    emit_stage_completed(
        state,
        "spec",
        "Plan synthesised",
        domain=spec.get("domain"),
        pattern=spec.get("pattern"),
    )

    return {
        **state,
        "contract_spec": spec,
        "current_step":  "Retrieving DAML patterns...",
        "progress":      26,
    }


def rag_node(state: dict) -> dict:
    logger.info("Node: RAG retrieval", job_id=state.get("job_id"))
    _push_status(state, "Retrieving DAML patterns...", 25)
    emit_log(state, "Retrieving relevant Daml patterns from knowledge base\u2026")
    try:
        context = fetch_rag_context(state["structured_intent"])
        emit_log(
            state,
            f"Loaded {len(context)} reference snippet(s) for code generation",
            level="success",
            count=len(context),
        )
        return {
            **state,
            "rag_context":  context,
            "current_step": "Generating DAML code...",
            "progress":     30,
        }
    except Exception as e:
        logger.warning("RAG retrieval failed, continuing without context", error=str(e))
        emit_log(state, f"Pattern retrieval skipped ({e}) \u2014 generating without RAG context", level="warn")
        return {
            **state,
            "rag_context":  [],
            "current_step": "Generating DAML code...",
            "progress":     30,
        }


def generate_node(state: dict) -> dict:
    logger.info("Node: generate", job_id=state.get("job_id"))
    _push_status(state, "Generating DAML code...", 35)
    emit_stage_started(state, "generate", "Generating Daml contract code\u2026")
    result = run_writer_agent(
        structured_intent=state["structured_intent"],
        rag_context=state.get("rag_context", []),
        contract_spec=state.get("contract_spec"),
    )
    if not result["success"]:
        logger.error("Generate node failed", error=result.get("error"))
        emit_stage_failed(state, "generate", result.get("error", "Writer agent failed"))
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
        emit_log(state, f"Injecting Propose-Accept pattern ({initiator} \u2192 {', '.join(acceptors)})")
        try:
            daml_code = inject_proposal_pattern(daml_code, initiator, acceptors)
            logger.info("Propose-Accept pattern injected", initiator=initiator, acceptors=acceptors)
        except Exception as e:
            logger.warning("Proposal injection failed, continuing with core template", error=str(e))
            emit_log(state, f"Proposal injection skipped: {e}", level="warn")

    emit_stage_completed(
        state,
        "generate",
        f"Daml code generated \u2014 {len(daml_code)} chars",
        code_length=len(daml_code),
    )
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
    emit_stage_started(state, "generate", "Generating multi-template Daml project\u2026")
    result = run_project_writer_agent(
        structured_intent=state["structured_intent"],
        rag_context=state.get("rag_context", []),
        contract_spec=state.get("contract_spec"),
    )
    if not result["success"]:
        logger.error("Project generate node failed", error=result.get("error"))
        emit_stage_failed(state, "generate", result.get("error", "Project writer agent failed"))
        return {
            **state,
            "error_message":  result.get("error", "Project writer agent failed"),
            "is_fatal_error": True,
            "current_step":   "Failed at project generation",
            "progress":       0,
        }

    files = result["files"]
    file_names = list(files.keys())
    preview = ", ".join(file_names[:5])
    suffix = "\u2026" if len(files) > 5 else ""
    emit_log(
        state,
        f"Created {len(files)} project file(s): {preview}{suffix}",
        count=len(files),
        files=file_names,
    )
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

    emit_stage_completed(
        state,
        "generate",
        f"Daml project generated \u2014 {len(files)} file(s), primary template '{result.get('primary_template', '')}'",
        file_count=len(files),
        primary_template=result.get("primary_template", ""),
    )
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
    if attempt == 1:
        emit_stage_started(state, "compile", "Compiling Daml project (\u2018daml build\u2019)\u2026")
    else:
        emit_log(state, f"Recompiling \u2014 attempt {attempt}/{_max_fix_attempts() + 1}", attempt=attempt)

    try:
        result = run_compile_agent(
            state["generated_code"], job_id,
            project_files=state.get("project_files"),
            daml_yaml=state.get("daml_yaml", ""),
        )
        if result["success"]:
            _push_status(state, "Compilation successful! Deploying...", 80)
            emit_stage_completed(
                state,
                "compile",
                f"Compilation succeeded on attempt {attempt}",
                attempts=attempt,
                dar_path=result.get("dar_path", ""),
            )
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
            errors = result.get("errors", []) or []
            err_preview = (errors[0].get("message", "") if errors else result.get("raw_error", ""))[:160]
            emit(
                state,
                "compile_failed",
                f"Compile failed on attempt {attempt} \u2014 {err_preview or 'see logs'}",
                level="warn",
                data={"attempt": attempt, "error_count": len(errors)},
            )
            return {
                **state,
                "compile_result":  result.get("raw_error", ""),
                "compile_success": False,
                "compile_errors":  errors,
                "dar_path":        "",
                "attempt_number":  attempt,
                "current_step":    f"Fixing errors (attempt {attempt}/{_max_fix_attempts()})...",
                "progress":        progress,
            }
    except Exception as e:
        logger.error("Compile node failed", error=str(e))
        emit(state, "compile_failed", f"Compile crashed: {e}", level="error")
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
    emit(
        state,
        "fix_started",
        f"Auto-fixing compile errors (attempt {attempt}/{_max_fix_attempts()})\u2026",
        data={"attempt": attempt, "max": _max_fix_attempts()},
    )

    result = run_fix_agent(
        daml_code=state["generated_code"],
        compile_errors=state.get("compile_errors", []),
        attempt_number=attempt,
    )
    if not result["success"]:
        logger.warning("Fix node failed", error=result.get("error"))
        emit(state, "fix_failed", f"Fix attempt {attempt} failed: {result.get('error', '')}", level="warn")
        return {
            **state,
            "current_step": f"Fix attempt {attempt} failed, retrying...",
        }
    emit(state, "fix_completed", f"Fix applied \u2014 retrying compile", level="success")
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
    emit(
        state,
        "fallback_used",
        "All AI fix attempts exhausted \u2014 deploying guaranteed-safe fallback template",
        level="warn",
    )

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
    emit_stage_started(state, "audit", "Running security audit & compliance analysis\u2026")

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

        # Surface high-severity findings as individual log lines so the user
        # sees *what* the audit caught, not just an aggregate score.
        findings = audit_result.get("findings", []) or []
        high_sev = [
            f for f in findings
            if (f.get("severity") or "").upper() in ("CRITICAL", "HIGH")
        ][:5]
        for f in high_sev:
            emit(
                state,
                "audit_finding",
                f"[{(f.get('severity') or '').upper()}] {f.get('title', 'Audit finding')}",
                level="warn" if (f.get("severity") or "").upper() == "HIGH" else "error",
                data={
                    "severity": f.get("severity"),
                    "category": f.get("category"),
                    "title": f.get("title"),
                },
            )

        emit_stage_completed(
            state,
            "audit",
            f"Audit complete — Security {security_score}/100, Compliance {compliance_score}/100, Enterprise {enterprise_score}/100",
            security_score=security_score,
            compliance_score=compliance_score,
            enterprise_score=enterprise_score,
            deploy_gate=deploy_gate,
            high_finding_count=len(high_sev),
        )
        if not deploy_gate:
            emit(
                state,
                "audit_gate_blocked",
                "Security gate is closed — deployment will be blocked unless on sandbox",
                level="warn",
                data={"deploy_gate": False},
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
        emit(state, "audit_skipped", f"Audit crashed ({e}) — continuing to deploy", level="warn")
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
            emit_stage_failed(state, "deploy", "Blocked by security gate — deployment refused")
            return {
                **state,
                "error_message":  "Security gate blocked deployment. Audit found critical vulnerabilities — fix them before deploying.",
                "is_fatal_error": True,
                "current_step":   "Blocked by security gate — not deployed",
                "progress":       90,
            }
        else:
            logger.warning("Security gate would block deployment but sandbox mode — proceeding anyway", job_id=state.get("job_id"))
            emit_log(state, "Sandbox mode: bypassing closed security gate", level="warn")

    _push_status(state, "Deploying to Canton ledger...", 90)
    emit_stage_started(
        state,
        "deploy",
        "Submitting compiled DAR to Canton ledger\u2026",
        canton_environment=state.get("canton_environment", "sandbox"),
    )

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
            emit_stage_completed(
                state,
                "deploy",
                f"Contract deployed \u2014 {result['contract_id'][:24]}\u2026",
                contract_id=result.get("contract_id"),
                package_id=result.get("package_id"),
                template_id=result.get("template_id"),
                explorer_link=result.get("explorer_link"),
            )
            emit_stage_started(state, "verify", "Verifying contract is active on the ledger\u2026")
            emit_stage_completed(
                state,
                "verify",
                "Contract verified on ledger",
                contract_id=result.get("contract_id"),
            )
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
            emit_stage_failed(state, "deploy", result.get("error", "Deployment failed"))
            return {
                **state,
                "error_message":  result.get("error", "Deployment failed"),
                "is_fatal_error": True,
                "current_step":   "Deployment failed",
                "progress":       80,
            }
    except Exception as e:
        logger.error("Deploy node failed", error=str(e))
        emit_stage_failed(state, "deploy", f"Deployment crashed: {e}")
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


def _route_after_compile(state: dict) -> Literal["audit", "fix", "fallback", "error"]:
    if state.get("compile_success"):
        return "audit"

    # If we already used fallback and it still fails, give up
    if state.get("fallback_used"):
        logger.error("Fallback contract also failed to compile", job_id=state.get("job_id"))
        return "error"

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
    graph.add_node("spec_synth",       spec_synth_node)
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

    graph.add_conditional_edges("intent", _route_after_intent, {"rag": "spec_synth", "error": "error"})
    graph.add_edge("spec_synth", "rag")
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
        {"audit": "audit", "fix": "fix", "fallback": "fallback", "error": "error"},
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
        "contract_spec":      None,
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

    # Emit a top-level pipeline_started event so the frontend can render the
    # stage strip immediately, even before the first node runs.
    emit(
        initial_state,
        "pipeline_started",
        f"Pipeline started on {canton_environment}",
        data={
            "stages": list(PIPELINE_STAGES),
            "canton_environment": canton_environment,
            "user_input_preview": (user_input or "")[:200],
        },
    )

    try:
        pipeline = build_pipeline()
        final_state = pipeline.invoke(initial_state, {"recursion_limit": 50})
    finally:
        # Always cleanup the callback
        _status_callbacks.pop(job_id, None)

    if final_state.get("contract_id"):
        derived_status = "complete"
    elif final_state.get("is_fatal_error") or final_state.get("error_message"):
        derived_status = "failed"
    else:
        derived_status = "complete"

    # Defensive branding: re-stamp the final code AFTER all transforms
    # (fix-loop, fallback, proposal injection) so the brand header always
    # reaches the user. ``prepend_brand_header`` is idempotent so this is
    # safe even when the writer already branded the output.
    spec_for_brand = final_state.get("contract_spec") or {}
    pattern = spec_for_brand.get("pattern") if isinstance(spec_for_brand, dict) else None
    domain = spec_for_brand.get("domain") if isinstance(spec_for_brand, dict) else None
    final_code = final_state.get("generated_code") or ""
    if final_code:
        final_state["generated_code"] = prepend_brand_header(
            final_code,
            pattern=pattern,
            domain=domain,
            module_name="Main",
        )
    project_files = final_state.get("project_files")
    if isinstance(project_files, dict) and project_files:
        for fname, code in list(project_files.items()):
            if not fname.endswith(".daml"):
                continue
            stem = fname.rsplit("/", 1)[-1].removesuffix(".daml")
            project_files[fname] = prepend_brand_header(
                code,
                pattern=pattern,
                domain=domain,
                module_name=stem,
            )
        final_state["project_files"] = project_files

    final_state["status"]     = derived_status
    final_state["daml_code"]  = final_state.get("generated_code", "")

    if derived_status == "complete":
        emit(
            final_state,
            "pipeline_completed",
            "Pipeline completed \u2014 contract deployed and verified",
            level="success",
            data={
                "contract_id": final_state.get("contract_id"),
                "explorer_link": final_state.get("explorer_link"),
                "attempts": final_state.get("attempt_number"),
            },
        )
    else:
        emit(
            final_state,
            "pipeline_failed",
            final_state.get("error_message") or "Pipeline failed",
            level="error",
            data={"attempts": final_state.get("attempt_number")},
        )

    logger.info(
        "Pipeline completed",
        job_id=job_id,
        status=derived_status,
        attempts=final_state.get("attempt_number"),
    )

    return final_state
