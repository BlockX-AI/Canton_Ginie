"""
Hybrid Security Auditor for DAML Smart Contracts.

Orchestrates:
1. LLM-based deep security analysis (audit_agent)
2. Multi-framework compliance analysis (compliance_engine)
3. Combined report generation (report_generator)

Produces enterprise-grade audit reports with executive summaries,
control attestations, and prioritized remediation roadmaps.
"""

import structlog
from datetime import datetime, timezone

from security.audit_agent import run_security_audit
from security.compliance_engine import run_compliance_analysis
from security.static_checks import detect_static_findings
from security.report_generator import (
    generate_json_report,
    generate_markdown_report,
    generate_html_report,
)

logger = structlog.get_logger()


def run_hybrid_audit(
    daml_code: str,
    contract_name: str = "Unknown",
    compliance_profile: str = "generic",
    skip_compliance: bool = False,
    skip_audit: bool = False,
) -> dict:
    """
    Run comprehensive hybrid audit: security + compliance + reporting.

    Args:
        daml_code: The DAML source code
        contract_name: Name of the contract being audited
        compliance_profile: Which compliance framework to check against
        skip_compliance: Skip compliance analysis (security only)
        skip_audit: Skip security audit (compliance only)

    Returns:
        dict with complete audit results, scores, reports in all formats
    """
    logger.info(
        "Starting hybrid audit",
        contract_name=contract_name,
        profile=compliance_profile,
    )
    start_time = datetime.now(timezone.utc)

    result = {
        "success": True,
        "contract_name": contract_name,
        "timestamp": start_time.isoformat(),
        "phases": {},
        "security_audit": None,
        "compliance_analysis": None,
        "combined_scores": {},
        "reports": {},
        "error": None,
    }

    # Phase 0: Static checks (deterministic, always run).
    # These are cheap regex scans that produce findings even when the
    # LLM audit later fails or times out. They merge into the security
    # audit's findings list under ``source: "static"`` so the report
    # generator and combined-score paths see them as first-class items.
    static_findings = detect_static_findings(daml_code)
    if static_findings:
        logger.info(
            "Static checks produced findings",
            count=len(static_findings),
            severities=[f.get("severity") for f in static_findings],
        )

    # Phase 1: Security Audit
    audit_result = None
    if not skip_audit:
        logger.info("Phase 1: Security audit")
        result["phases"]["security_audit"] = {"started": datetime.now(timezone.utc).isoformat()}
        audit_result = run_security_audit(daml_code, contract_name)
        result["security_audit"] = audit_result
        result["phases"]["security_audit"]["completed"] = datetime.now(timezone.utc).isoformat()
        result["phases"]["security_audit"]["status"] = "success" if audit_result["success"] else "failed"

        if not audit_result["success"]:
            logger.warning("Security audit failed", error=audit_result.get("error"))

    # Merge static findings into the audit_result. We do this even when
    # the LLM audit failed entirely so deploy_gate has *something*
    # deterministic to evaluate against; a hung Anthropic call should
    # never silently turn into "no security issues found".
    if static_findings:
        if audit_result is None:
            audit_result = {
                "success": True,
                "audit_report": {
                    "contractName": contract_name,
                    "language": "DAML",
                    "platform": "Canton",
                    "findings": [],
                    "auditor": "Ginie Static Checker",
                    "version": "2.0",
                },
                "security_score": 100,
                "executive_summary": {},
                "findings_count": 0,
                "error": None,
            }
            result["security_audit"] = audit_result
            result["phases"]["security_audit"] = {
                "started": start_time.isoformat(),
                "completed": datetime.now(timezone.utc).isoformat(),
                "status": "static-only",
            }

        report = audit_result.setdefault("audit_report", {})
        existing = report.setdefault("findings", [])
        # Avoid duplicates if run_security_audit somehow already returned
        # an item with the same id (e.g. on a retry).
        existing_ids = {f.get("id") for f in existing if isinstance(f, dict)}
        for sf in static_findings:
            if sf.get("id") not in existing_ids:
                existing.append(sf)

        # Re-derive the deterministic score / executive summary so the
        # newly-merged findings count toward the gate.
        from security.audit_agent import (
            _compute_security_score,
            _build_executive_summary,
        )
        merged_findings = report["findings"]
        new_score = _compute_security_score(merged_findings)
        audit_result["security_score"] = new_score
        audit_result["findings_count"] = len(merged_findings)
        audit_result["executive_summary"] = _build_executive_summary(merged_findings, new_score)
        report["executiveSummary"] = audit_result["executive_summary"]

    # Phase 2: Compliance Analysis
    compliance_result = None
    if not skip_compliance:
        logger.info("Phase 2: Compliance analysis", profile=compliance_profile)
        result["phases"]["compliance_analysis"] = {"started": datetime.now(timezone.utc).isoformat()}
        compliance_result = run_compliance_analysis(daml_code, contract_name, compliance_profile)
        result["compliance_analysis"] = compliance_result
        result["phases"]["compliance_analysis"]["completed"] = datetime.now(timezone.utc).isoformat()
        result["phases"]["compliance_analysis"]["status"] = "success" if compliance_result["success"] else "failed"

        if not compliance_result["success"]:
            logger.warning("Compliance analysis failed", error=compliance_result.get("error"))

    # Phase 3: Combined Scoring
    security_score = audit_result.get("security_score", 0) if audit_result and audit_result.get("success") else None
    compliance_score = compliance_result.get("compliance_score", 0) if compliance_result and compliance_result.get("success") else None

    combined = {
        "security_score": security_score,
        "compliance_score": compliance_score,
        "compliance_profile": compliance_profile,
    }

    # Overall enterprise readiness
    if security_score is not None and compliance_score is not None:
        combined["enterprise_score"] = round((security_score * 0.6 + compliance_score * 0.4), 1)
        if combined["enterprise_score"] >= 85 and security_score >= 80 and compliance_score >= 80:
            combined["enterprise_readiness"] = "READY"
        elif combined["enterprise_score"] >= 65:
            combined["enterprise_readiness"] = "CONDITIONAL"
        else:
            combined["enterprise_readiness"] = "NOT_READY"
    elif security_score is not None:
        combined["enterprise_score"] = security_score
        combined["enterprise_readiness"] = "READY" if security_score >= 85 else "CONDITIONAL" if security_score >= 65 else "NOT_READY"
    elif compliance_score is not None:
        combined["enterprise_score"] = compliance_score
        combined["enterprise_readiness"] = "READY" if compliance_score >= 85 else "CONDITIONAL" if compliance_score >= 65 else "NOT_READY"

    # Deployment gate.
    #
    # Apr-30 regression: when the LLM audit returned non-JSON twice,
    # ``security_score`` was ``None`` and the gate previously evaluated
    # ``True`` via the ``or security_score is None`` clause. A contract
    # with an UNKNOWN security score then shipped to production with
    # ``readiness=CONDITIONAL`` but no signal to the deploy agent that
    # the audit had silently failed. We now explicitly BLOCK deploy
    # when we don't have a security score, and also block when
    # deterministic static-check findings flagged HIGH severity even
    # if the LLM phase failed \u2014 those findings are authoritative
    # on their own.
    sec_rec = (audit_result or {}).get("executive_summary", {}).get("recommendation", "")
    combined["deploy_gate"] = sec_rec in ("DEPLOY_READY",) and security_score is not None
    if audit_result and audit_result.get("success"):
        crit = audit_result.get("executive_summary", {}).get("criticalIssues", 0)
        if crit > 0:
            combined["deploy_gate"] = False
    # If the LLM audit failed entirely but static checks produced
    # findings, surface the static severity as the authority.
    if security_score is None:
        has_high = any(
            (f.get("severity") or "").upper() in ("HIGH", "CRITICAL")
            for f in static_findings
        )
        combined["deploy_gate"] = False
        combined["enterprise_readiness"] = "NOT_READY" if has_high else "CONDITIONAL"
        combined["audit_degraded"] = True

    result["combined_scores"] = combined

    # Phase 4: Report Generation
    logger.info("Phase 3: Generating reports")
    try:
        result["reports"] = {
            "json": generate_json_report(audit_result, compliance_result),
            "markdown": generate_markdown_report(audit_result, compliance_result),
            "html": generate_html_report(audit_result, compliance_result),
        }
    except Exception as e:
        logger.error("Report generation failed", error=str(e))
        result["reports"] = {"json": "{}", "markdown": "", "html": ""}

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    result["elapsed_seconds"] = round(elapsed, 1)

    logger.info(
        "Hybrid audit completed",
        contract_name=contract_name,
        security_score=security_score,
        compliance_score=compliance_score,
        enterprise_score=combined.get("enterprise_score"),
        readiness=combined.get("enterprise_readiness"),
        elapsed_seconds=result["elapsed_seconds"],
    )

    return result
