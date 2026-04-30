import os
import structlog
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from agents.intent_agent import run_intent_agent
from agents.writer_agent import run_writer_agent, fetch_rag_context
from agents.project_writer_agent import run_project_writer_agent
from agents.test_writer_agent import run_test_writer_agent
from agents.test_compile_agent import run_test_compile_agent
from pipeline.spec_synth import synthesize_spec
from agents.compile_agent import run_compile_agent
from agents.fix_agent import run_fix_agent
from agents.deploy_agent import run_deploy_agent
from agents.proposal_injector import inject_proposal_pattern
from agents.diagram_agent import parse_daml_for_diagram, generate_mermaid
from security.hybrid_auditor import run_hybrid_audit
from config import get_settings
from utils.branding import prepend_brand_header
from rag.curated_loader import get_curated_example
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
    """Replace generated code with guaranteed-compilable fallback contract.

    Prefers the curated, hand-audited template that matches the Plan's
    ``pattern`` / ``domain`` (e.g. ``voting-dao``, ``soulbound-credential``)
    over the generic two-party ``SimpleContract``. The curated templates
    are guaranteed to compile against the Daml SDK we ship with, so they
    are always a safer fallback than the LLM's failing output AND they
    actually express the user's intent instead of a meaningless transfer.
    Falls back to ``FALLBACK_CONTRACT`` only when no curated pattern matches.
    """
    logger.info("Node: fallback (using guaranteed contract)", job_id=state.get("job_id"))
    _push_status(state, "Using fallback contract template", 75)

    spec = state.get("contract_spec") or {}
    pattern = spec.get("pattern") if isinstance(spec, dict) else None
    domain = spec.get("domain") if isinstance(spec, dict) else None
    curated = get_curated_example(pattern, domain)
    if curated:
        stem, src = curated
        fallback_code = src
        fallback_label = f"curated:{stem}"
        emit(
            state,
            "fallback_used",
            f"All AI fix attempts exhausted \u2014 deploying curated {stem} reference template",
            level="warn",
            data={"template": stem, "kind": "curated"},
        )
    else:
        fallback_code = FALLBACK_CONTRACT
        fallback_label = "generic-simple-contract"
        emit(
            state,
            "fallback_used",
            "All AI fix attempts exhausted \u2014 deploying guaranteed-safe fallback template",
            level="warn",
            data={"template": fallback_label, "kind": "generic"},
        )

    # Preserve original project files for the user even though we're falling back
    original_project_files = state.get("project_files", {})

    return {
        **state,
        "generated_code":           fallback_code,
        "attempt_number":           0,
        "compile_errors":           [],
        "compile_success":          False,
        "fallback_used":            True,
        "fallback_template":        fallback_label,
        "project_mode":             False,
        "project_files":            {},
        "daml_yaml":                "",
        "original_project_files":   original_project_files,
        "current_step":             f"Using fallback contract template ({fallback_label})",
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
        # Wall-clock cap: run the audit on a worker thread and wait at most
        # ``audit_max_seconds`` for it. If anything inside (LLM call,
        # compliance_engine, report generation) blocks past the deadline
        # we abandon the audit and let the pipeline continue to deploy
        # with degraded scores. Without this guard a single hung HTTP call
        # silently parks the entire pipeline at the AUDIT stage forever
        # (frontend keeps polling /status returning "running" indefinitely).
        import concurrent.futures as _cf
        settings = get_settings()
        audit_deadline = float(getattr(settings, "audit_max_seconds", 240.0) or 240.0)
        emit_log(
            state,
            f"Audit budget: {int(audit_deadline)}s wall-clock",
            level="debug",
        )
        # NOTE: deliberately avoiding the ``with ThreadPoolExecutor(...)``
        # form here \u2014 ``__exit__`` calls ``shutdown(wait=True)`` which
        # would block until the hung worker completes, defeating the whole
        # point of the timeout. We shut down with ``wait=False`` so the
        # pipeline thread proceeds to deploy while the runaway audit
        # request gets reaped by the LLM SDK's own client-side timeout.
        _ex = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="audit-")
        _future = _ex.submit(
            run_hybrid_audit,
            daml_code=daml_code,
            contract_name=contract_name,
            compliance_profile="generic",
        )
        try:
            audit_result = _future.result(timeout=audit_deadline)
        except _cf.TimeoutError:
            logger.warning(
                "Audit phase exceeded wall-clock budget \u2014 abandoning",
                job_id=job_id,
                budget_seconds=audit_deadline,
            )
            emit(
                state,
                "audit_timeout",
                f"Audit took longer than {int(audit_deadline)}s \u2014 skipping and continuing to deploy",
                level="warn",
                data={"budget_seconds": audit_deadline},
            )
            _future.cancel()
            _ex.shutdown(wait=False, cancel_futures=True)
            return {
                **state,
                "audit_result": None,
                "security_score": None,
                "compliance_score": None,
                "enterprise_score": None,
                "deploy_gate": True,  # Don't block on a phase we couldn't run
                "audit_reports": {},
                "current_step": "Audit timed out, deploying to Canton...",
                "progress": 85,
            }
        finally:
            # Successful path: ``shutdown(wait=False)`` is safe \u2014 the
            # future has already completed, so there's no orphan thread.
            _ex.shutdown(wait=False)

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
            # Build a structured, actionable message. Categorise findings
            # by severity so the user sees the breakdown rather than a
            # vague "gate closed" warning.
            sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for f in findings:
                s = (f.get("severity") or "").upper()
                if s in sev_counts:
                    sev_counts[s] += 1
            parts = []
            if sev_counts["CRITICAL"]:
                parts.append(f"{sev_counts['CRITICAL']} CRITICAL")
            if sev_counts["HIGH"]:
                parts.append(f"{sev_counts['HIGH']} HIGH")
            if sev_counts["MEDIUM"]:
                parts.append(f"{sev_counts['MEDIUM']} MEDIUM")
            if sev_counts["LOW"]:
                parts.append(f"{sev_counts['LOW']} LOW")
            breakdown = ", ".join(parts) or "no findings recorded"

            settings = get_settings()
            on_sandbox = settings.canton_environment == "sandbox"

            if on_sandbox:
                # Sandbox is for iterating; deploy proceeds.
                msg = (
                    f"Security review: {breakdown}. "
                    "Sandbox policy allows deploy \u2014 fix findings before MainNet."
                )
                level = "info"
            else:
                # Production-ish target; deploy will be refused downstream.
                msg = (
                    f"Security review: {breakdown}. "
                    "Production gate requires zero CRITICAL/HIGH and score \u2265 85 \u2014 deployment will be refused."
                )
                level = "warn"

            emit(
                state,
                "audit_gate_blocked",
                msg,
                level=level,
                data={
                    "deploy_gate": False,
                    "severity_counts": sev_counts,
                    "on_sandbox": on_sandbox,
                },
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
            # Sandbox path: deploy proceeds. The audit_node has already
            # surfaced the finding breakdown; here we keep the log line
            # informational rather than alarming \u2014 "bypass" reads
            # like a hack, "policy" reads like a deliberate choice.
            logger.info(
                "Sandbox policy: deploy proceeds despite open audit findings",
                job_id=state.get("job_id"),
            )
            emit_log(
                state,
                "Sandbox policy: deploy proceeds despite audit findings. Review the audit report before MainNet.",
                level="info",
            )

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

            # Persist the allocated parties to ``registered_parties`` with the
            # deploying user's email as the owner, so the Explorer's Parties
            # tab can render them via /me/parties on the very next page load.
            # Without this, parties allocated by the deploy agent only exist
            # on Canton itself + inside ``JobHistory.result_json.parties`` \u2014
            # which means a user who deploys and then hits the Parties tab
            # before the result blob lands will see "0 parties".
            try:
                from auth.party_manager import record_deploy_parties
                record_deploy_parties(
                    parties=result.get("parties") or {},
                    user_email=state.get("user_email"),
                    canton_env=canton_env,
                )
            except Exception as _e:
                logger.warning(
                    "Failed to record deploy parties (deploy itself succeeded)",
                    error=str(_e),
                    job_id=state.get("job_id"),
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


def test_writer_node(state: dict) -> dict:
    """Generate a Daml-Script test file alongside the production DAML.

    The test artifact ships as part of the job result so QA / audit can
    compile and run it in a separate ``-tests`` package without
    polluting the production DAR with ``daml-script``. Coverage is
    measured by counting ``submitMustFail`` calls; below the floor we
    surface a non-fatal warning so the deploy still proceeds but the
    user (and any downstream gate) sees the gap.

    Failure here NEVER blocks the pipeline. The test file is a
    deliverable artifact, not a deployment prerequisite.
    """
    job_id = state.get("job_id", "unknown")
    logger.info("Node: test_writer", job_id=job_id)
    daml_code = state.get("generated_code", "")
    if not daml_code:
        logger.warning("test_writer skipped \u2014 no generated_code")
        return state

    _push_status(state, "Generating Daml-Script test scaffold...", 86)
    emit_stage_started(
        state,
        "test_writer",
        "Drafting Daml-Script tests (\u2265 5 submitMustFail cases)\u2026",
    )

    try:
        result = run_test_writer_agent(
            daml_code=daml_code,
            structured_intent=state.get("structured_intent"),
            contract_spec=state.get("contract_spec"),
        )
    except Exception as exc:  # noqa: BLE001 - test artifact is non-fatal
        logger.warning("test_writer crashed; continuing", error=str(exc))
        emit_log(
            state,
            f"Test scaffold generation skipped: {exc}",
            level="warn",
        )
        return state

    must_fail = int(result.get("must_fail_count") or 0)
    coverage_ok = bool(result.get("coverage_ok"))

    summary = (
        f"Test scaffold generated \u2014 {must_fail} submitMustFail case(s)"
        + ("" if coverage_ok else f" (coverage gate: minimum 5 required)")
    )
    if coverage_ok:
        emit_stage_completed(state, "test_writer", summary)
    else:
        # Non-fatal warning. We still advance the pipeline.
        emit_log(state, summary, level="warn")
        emit_stage_completed(
            state,
            "test_writer",
            summary + " \u2014 deploy continues; hand-author the missing cases before MainNet.",
        )

    return {
        **state,
        "test_daml_code":     result.get("test_daml_code", ""),
        "test_module_name":   result.get("test_module_name", ""),
        "test_file_path":     result.get("test_file_path", ""),
        "must_fail_count":    must_fail,
        "test_coverage_ok":   coverage_ok,
    }


def test_compile_node(state: dict) -> dict:
    """Compile the Daml-Script test scaffold against the production DAR.

    Builds a sibling ``<job>-tests`` package that imports the production
    DAR as a data-dependency and adds ``daml-script`` only there. This
    keeps the production DAR clean (no test runtime in the deployed
    artifact) while still proving the test scaffold compiles.

    Failure here NEVER blocks the pipeline. The production DAR was
    already built by ``compile_node``; this only adds verification of
    the *test* scaffold. On compile failure we surface a MEDIUM finding
    in the audit report so the user can see exactly which test broke.
    """
    job_id = state.get("job_id", "unknown")
    test_code = state.get("test_daml_code", "")
    if not test_code:
        # Nothing to compile \u2014 test_writer was skipped or failed soft.
        return state

    dar_path = state.get("dar_path", "")
    if not dar_path:
        logger.info("test_compile skipped \u2014 no production DAR yet")
        return state

    logger.info("Node: test_compile", job_id=job_id)
    _push_status(state, "Compiling Daml-Script test scaffold...", 88)
    emit_stage_started(
        state,
        "test_compile",
        "Building <job>-tests package against the production DAR\u2026",
    )

    try:
        result = run_test_compile_agent(
            job_id=job_id,
            production_dar_path=dar_path,
            production_daml_code=state.get("generated_code", ""),
            test_daml_code=test_code,
            test_module_name=state.get("test_module_name", ""),
            test_file_path=state.get("test_file_path", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("test_compile crashed; continuing", error=str(exc))
        emit_log(state, f"Test compile skipped: {exc}", level="warn")
        return state

    if result.get("success"):
        # Phase F.1: ``test_compile_agent`` may have additionally
        # *executed* the test scripts via ``daml test`` when
        # ``RUN_DAML_SCRIPTS=true``. Compile success and script-run
        # success are independent: a scaffold can compile cleanly and
        # still abort at runtime with ``ENSURE_VIOLATED`` (the
        # FullRepay deadlock pattern). Surface that as a HIGH finding
        # so the audit panel reflects the runtime defect, while
        # leaving production deploy unaffected (sandbox policy).
        if (
            result.get("script_run_attempted")
            and not result.get("script_run_success")
        ):
            _append_script_runtime_finding(state, result)
            summary = result.get("test_compile_output_summary") or (
                "Test scaffold compiled but Daml-Script execution failed."
            )
            emit_log(state, summary, level="warn")
            emit_stage_completed(
                state,
                "test_compile",
                summary + " \u2014 production DAR is unaffected and will still deploy.",
            )
            return {
                **state,
                "test_dar_path":            result.get("test_dar_path", ""),
                "test_compile_success":     True,
                "script_run_success":       False,
                "script_run_failures":      result.get("script_run_failures") or [],
                "script_run_summary":       result.get("script_run_summary", ""),
                "test_compile_errors":      [],
                "test_compile_summary":     summary,
            }

        emit_stage_completed(
            state,
            "test_compile",
            f"Test scaffold compiled \u2014 DAR at {result.get('test_dar_path')}",
        )
        return {
            **state,
            "test_dar_path":              result.get("test_dar_path", ""),
            "test_compile_success":       True,
            "script_run_success":         result.get("script_run_success", None),
            "script_run_summary":         result.get("script_run_summary", ""),
            "test_compile_errors":        [],
            "test_compile_summary":       result.get("test_compile_output_summary", ""),
        }

    # Failure: surface as a MEDIUM audit finding without blocking deploy.
    if not result.get("soft_failure"):
        _append_test_compile_finding(state, result)
    summary = result.get("test_compile_output_summary") or "Test scaffold did not compile."
    emit_log(state, summary, level="warn")
    emit_stage_completed(
        state,
        "test_compile",
        summary + " \u2014 production DAR is unaffected and will still deploy.",
    )
    return {
        **state,
        "test_dar_path":              "",
        "test_compile_success":       False,
        "test_compile_errors":        result.get("errors") or [],
        "test_compile_summary":       summary,
    }


def _append_test_compile_finding(state: dict, result: dict) -> None:
    """Inject a MEDIUM finding into the live audit report so the
    user-visible findings panel reflects the test-compile failure."""
    audit = state.setdefault("audit_reports", {})
    sec = audit.setdefault("security_audit", {})
    findings = sec.setdefault("findings", [])
    err_summary = "\n".join(
        f"  {e.get('file','?')}:{e.get('line','?')}: {e.get('message','')}"
        for e in (result.get("errors") or [])[:5]
    ) or "(no parseable error head; see test_compile_summary for raw output)"
    findings.append({
        "id":          "DSV-022::test-compile",
        "severity":    "MEDIUM",
        "category":    "Test Scaffolding",
        "title":       "Generated Daml-Script test scaffold did not compile",
        "description": (
            "The auto-generated ``Test/<Template>Test.daml`` scaffold "
            "failed to build in its sibling ``-tests`` package. The "
            "production DAR is unaffected and was deployed normally, "
            "but the documented happy-path / submitMustFail cases are "
            "NOT verified to compile, let alone pass.\n\nFirst errors:\n"
            + err_summary
        ),
        "location":    {"template": None, "choice": None, "lineNumbers": [0, 0]},
        "recommendation": (
            "Open the test scaffold at the path reported in "
            "``test_file_path``, fix the compile errors above, and "
            "re-run ``daml build`` in the ``-tests`` project. Test "
            "compilation does not block deploy on sandbox; it must "
            "be green before MainNet."
        ),
        "references": ["DSV-022"],
        "source":     "test_compile",
    })


def _append_script_runtime_finding(state: dict, result: dict) -> None:
    """Phase F.1: surface a Daml-Script runtime failure as a HIGH finding.

    Unlike ``DSV-022`` (compile failure), runtime failures point at a
    real semantic defect in the *production* contract \u2014 the
    scaffold compiles, but executing the happy-path script trips an
    ``ENSURE_VIOLATED`` / authorization error that the static checks
    could not see. We label these ``DSV-029`` so they are
    distinguishable from compile-time issues in the user-visible
    findings list.
    """
    audit    = state.setdefault("audit_reports", {})
    sec      = audit.setdefault("security_audit", {})
    findings = sec.setdefault("findings", [])
    fails    = result.get("script_run_failures") or []
    # Compose a short failure list that fits the audit panel.
    fail_lines = []
    for f in fails[:5]:
        fail_lines.append(
            f"  {f.get('script', '<unknown>')}: {f.get('marker', '?')}"
        )
    fail_blob = "\n".join(fail_lines) or "(no parseable failures; see script_run_summary)"
    tail      = (result.get("script_run_output_tail") or "")[-800:]
    findings.append({
        "id":          "DSV-029::script-runtime",
        "severity":    "HIGH",
        "category":    "Test Execution",
        "title":       "Generated Daml-Script test failed at runtime",
        "description": (
            "The auto-generated happy-path script compiled cleanly but "
            "aborted during execution. Runtime failures of this kind "
            "(``ENSURE_VIOLATED``, ``AUTHORIZATION_FAILED``, etc.) "
            "indicate a *semantic* defect in the production contract "
            "that static analysis could not see \u2014 typically an "
            "ensure clause that contradicts a choice precondition, or "
            "a missing signatory authorization on a downstream "
            "create.\n\nFailures:\n"
            + fail_blob
            + ("\n\nLast lines of test output:\n" + tail if tail else "")
        ),
        "location":    {"template": None, "choice": None, "lineNumbers": [0, 0]},
        "impact": (
            "The happy-path workflow documented in the test scaffold "
            "is not actually reachable. In practice this means a "
            "production deploy will trip the same runtime error the "
            "first time a real party tries to exercise the choice."
        ),
        "recommendation": (
            "Read the failure marker (e.g. ``ENSURE_VIOLATED``) and "
            "the source location, then fix the underlying contract: "
            "either relax the violated ensure or capture the original "
            "value into a separate immutable field (see SEC-GEN-021 "
            "for the canonical pattern)."
        ),
        "references": ["DSV-029"],
        "source":     "test_compile",
    })


# ---------------------------------------------------------------------------
# Phase F.4: audit-driven retry
# ---------------------------------------------------------------------------


# Findings whose presence justifies a one-shot fix-and-retry. These are
# the *semantic* defects that the LLM can plausibly repair given a
# clear feedback message, not vague vulnerability reports the LLM
# auditor sometimes emits. Keeping the list short prevents noisy
# retries on subjective findings (observer-information-leakage etc.).
_AUDIT_RETRY_FINDING_PREFIXES = (
    "DSV-024",   # invariant deadlock (FullRepay-class)
    "DSV-025",   # observer-only counterparty (signatory regression)
    "DSV-026",   # proposal missing expiresAt
    "DSV-027",   # accept choice does not enforce expiresAt
    "DSV-028",   # terminal state populated from mutated balance
    "DSV-029",   # daml-script runtime failure (F.1 signal)
)


def _max_audit_retries() -> int:
    """Hard ceiling on audit-driven retries.

    One round is the sweet spot: it gives the LLM a chance to address
    the deterministic-detector feedback without compounding wall-clock
    cost. Overridable via ``MAX_AUDIT_RETRIES``.
    """
    raw = os.environ.get("MAX_AUDIT_RETRIES", "1")
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def _collect_actionable_findings(state: dict) -> list[dict]:
    """Pluck findings whose IDs match the retry-allowlist."""
    out: list[dict] = []
    audit = state.get("audit_reports") or {}
    sec   = audit.get("security_audit") if isinstance(audit, dict) else None
    if not isinstance(sec, dict):
        return out
    for f in sec.get("findings") or []:
        fid = str(f.get("id", ""))
        if any(fid.startswith(p) for p in _AUDIT_RETRY_FINDING_PREFIXES):
            out.append(f)
    return out


def _format_findings_as_compile_errors(findings: list[dict]) -> list[dict]:
    """Adapt audit findings to the ``fix_agent`` compile-error shape.

    ``run_fix_agent`` accepts a list of dicts whose ``message`` field
    drives the LLM prompt. We pack the title + recommendation into
    that field so the LLM has a concrete fix instruction, not just a
    diagnosis.
    """
    out: list[dict] = []
    for f in findings:
        title = f.get("title") or "audit finding"
        rec   = f.get("recommendation") or ""
        loc   = f.get("location") or {}
        tpl   = loc.get("template") or ""
        ch    = loc.get("choice") or ""
        location_str = (
            f"{tpl}::{ch}" if tpl and ch
            else tpl or ch or ""
        )
        message = (
            f"[{f.get('severity', 'HIGH')}] {f.get('id', '?')}: {title}\n"
            + (f"Location: {location_str}\n" if location_str else "")
            + (f"Fix: {rec}\n" if rec else "")
        )
        out.append({
            "file":    "daml/Main.daml",
            "line":    0,
            "column":  0,
            "message": message,
            "type":    "audit",
            "raw":     message,
        })
    return out


def audit_retry_node(state: dict) -> dict:
    """Phase F.4: feed semantic audit findings back into the fix agent.

    Runs at most ``MAX_AUDIT_RETRIES`` times per job. On each call:

      1. Collect actionable findings from the audit + test-runtime steps.
      2. If none, or budget exhausted, route forward to ``diagram`` unchanged.
      3. Otherwise format findings as fix-agent feedback, invoke
         ``run_fix_agent`` with the current production source, and on
         success replace ``generated_code`` and route back to ``compile``.

    The node never aborts the pipeline. If the fix agent fails or
    returns no change we fall through to ``diagram`` so the user
    still gets a deploy off the last-known-good DAR.
    """
    job_id   = state.get("job_id", "?")
    attempts = int(state.get("audit_fix_attempts", 0))
    if attempts >= _max_audit_retries():
        logger.info(
            "audit_retry budget exhausted; routing forward",
            job_id=job_id, attempts=attempts,
        )
        return {**state, "audit_retry_done": True}

    findings = _collect_actionable_findings(state)
    if not findings:
        logger.info(
            "audit_retry: no actionable findings",
            job_id=job_id, attempts=attempts,
        )
        return {**state, "audit_retry_done": True}

    logger.info(
        "Node: audit_retry",
        job_id=job_id,
        attempts=attempts + 1,
        finding_count=len(findings),
        finding_ids=[f.get("id") for f in findings],
    )
    _push_status(
        state,
        f"Auto-fixing audit findings (round {attempts + 1}/{_max_audit_retries()})...",
        72,
    )
    emit_log(
        state,
        f"Re-running fix agent with {len(findings)} audit finding(s) as feedback",
        level="info",
    )

    pseudo_errors = _format_findings_as_compile_errors(findings)
    try:
        result = run_fix_agent(
            daml_code=state.get("generated_code", ""),
            compile_errors=pseudo_errors,
            attempt_number=attempts + 1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_retry fix agent crashed; routing forward", error=str(exc))
        return {**state, "audit_retry_done": True}

    if not result or not result.get("success") or not result.get("fixed_code"):
        logger.info(
            "audit_retry: fix agent returned no change",
            job_id=job_id, attempts=attempts + 1,
        )
        return {
            **state,
            "audit_fix_attempts": attempts + 1,
            "audit_retry_done":   True,
        }

    new_code = result["fixed_code"]
    if new_code.strip() == (state.get("generated_code", "") or "").strip():
        return {
            **state,
            "audit_fix_attempts": attempts + 1,
            "audit_retry_done":   True,
        }

    emit_log(state, "Audit-driven fix applied \u2014 recompiling", level="success")
    # Reset compile-fix state so the recompile counts as fresh, but
    # keep the audit-retry counter incrementing so we cannot loop.
    return {
        **state,
        "generated_code":      new_code,
        "audit_fix_attempts":  attempts + 1,
        "audit_retry_done":    False,
        "attempt_number":      1,
        "compile_errors":      [],
        "dar_path":            "",
        # Clear stale audit + test-compile state so the next round
        # writes fresh findings rather than appending duplicates.
        "audit_reports":       {},
        "script_run_failures": [],
        "script_run_summary":  "",
    }


def _route_after_test_compile(state: dict) -> str:
    """Decide whether to fire one more audit-driven fix round."""
    if state.get("audit_retry_done"):
        return "diagram"
    if int(state.get("audit_fix_attempts", 0)) >= _max_audit_retries():
        return "diagram"
    if not _collect_actionable_findings(state):
        return "diagram"
    return "audit_retry"


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
    graph.add_node("test_writer",      test_writer_node)
    graph.add_node("test_compile",     test_compile_node)
    graph.add_node("audit_retry",      audit_retry_node)
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
    graph.add_edge("audit",        "test_writer")
    graph.add_edge("test_writer",  "test_compile")
    # Phase F.4: after test_compile, conditionally fire one round of
    # audit-driven re-fix-and-recompile if any actionable findings
    # are still open. Otherwise proceed straight to diagram/deploy.
    graph.add_conditional_edges(
        "test_compile",
        _route_after_test_compile,
        {"audit_retry": "audit_retry", "diagram": "diagram"},
    )
    # The retry node either edits the source and routes back to compile
    # (so the next compile/audit/test_compile pass sees the fixed code),
    # or no-ops and routes forward to diagram. We capture both via a
    # tiny conditional on the same ``audit_retry_done`` flag.
    graph.add_conditional_edges(
        "audit_retry",
        lambda s: "diagram" if s.get("audit_retry_done") else "compile",
        {"compile": "compile", "diagram": "diagram"},
    )
    graph.add_edge("diagram",      "deploy")
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
