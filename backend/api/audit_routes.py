"""
Enterprise Audit & Compliance API endpoints.

POST /api/audit/analyze       — Run security audit on DAML code
POST /api/audit/byJob         — Run audit on a completed job's code
POST /api/compliance/analyze  — Run compliance analysis on DAML code
POST /api/compliance/byJob    — Run compliance on a completed job's code
GET  /api/audit/report/{job}  — Get audit reports (json/md/html) for a job
"""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from security.compliance_engine import run_compliance_analysis, VALID_PROFILES
from security.hybrid_auditor import run_hybrid_audit

logger = structlog.get_logger()
audit_router = APIRouter()


# ── Request / Response Models ────────────────────────────────────────────────

class AuditRequest(BaseModel):
    code: str = Field(..., min_length=10, description="DAML source code to audit")
    contract_name: str = Field(default="Contract", description="Name of the contract")
    compliance_profile: str = Field(default="generic", description="Compliance profile")
    skip_compliance: bool = Field(default=False, description="Skip compliance analysis")
    skip_audit: bool = Field(default=False, description="Skip security audit")


class AuditByJobRequest(BaseModel):
    job_id: str = Field(..., description="Job ID of a completed pipeline run")
    compliance_profile: str = Field(default="generic")
    skip_compliance: bool = Field(default=False)
    skip_audit: bool = Field(default=False)


class ComplianceRequest(BaseModel):
    code: str = Field(..., min_length=10, description="DAML source code")
    contract_name: str = Field(default="Contract")
    profile: str = Field(default="generic", description="Compliance profile")


class ComplianceByJobRequest(BaseModel):
    job_id: str = Field(...)
    profile: str = Field(default="generic")


class AuditResponse(BaseModel):
    success: bool
    security_score: Optional[int] = None
    compliance_score: Optional[int] = None
    enterprise_score: Optional[float] = None
    enterprise_readiness: Optional[str] = None
    deploy_gate: Optional[bool] = None
    executive_summary: Optional[dict] = None
    compliance_summary: Optional[dict] = None
    findings_count: Optional[int] = None
    audit_report: Optional[dict] = None
    compliance_report: Optional[dict] = None
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None


class ComplianceResponse(BaseModel):
    success: bool
    compliance_score: Optional[int] = None
    profile: Optional[str] = None
    executive_summary: Optional[dict] = None
    compliance_report: Optional[dict] = None
    error: Optional[str] = None


class ReportResponse(BaseModel):
    success: bool
    job_id: str
    formats_available: list = []
    json_report: Optional[str] = None
    markdown_report: Optional[str] = None
    html_report: Optional[str] = None
    error: Optional[str] = None


# ── Helper to fetch job data ─────────────────────────────────────────────────

def _get_job_data(job_id: str) -> dict:
    """Fetch job data from Redis or in-memory store."""
    from api.routes import _get_job, _in_memory_jobs
    data = _get_job(job_id) or _in_memory_jobs.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return data


# ── Audit Endpoints ──────────────────────────────────────────────────────────

@audit_router.post("/audit/analyze", response_model=AuditResponse)
async def audit_analyze(request: AuditRequest):
    """Run full hybrid audit (security + compliance) on provided DAML code."""
    logger.info("API: audit/analyze", contract_name=request.contract_name)

    result = run_hybrid_audit(
        daml_code=request.code,
        contract_name=request.contract_name,
        compliance_profile=request.compliance_profile,
        skip_compliance=request.skip_compliance,
        skip_audit=request.skip_audit,
    )

    combined = result.get("combined_scores", {})
    sec = result.get("security_audit") or {}
    comp = result.get("compliance_analysis") or {}

    return AuditResponse(
        success=result.get("success", False),
        security_score=combined.get("security_score"),
        compliance_score=combined.get("compliance_score"),
        enterprise_score=combined.get("enterprise_score"),
        enterprise_readiness=combined.get("enterprise_readiness"),
        deploy_gate=combined.get("deploy_gate"),
        executive_summary=sec.get("executive_summary"),
        compliance_summary=comp.get("executive_summary"),
        findings_count=sec.get("findings_count"),
        audit_report=sec.get("audit_report"),
        compliance_report=comp.get("compliance_report"),
        elapsed_seconds=result.get("elapsed_seconds"),
        error=result.get("error"),
    )


@audit_router.post("/audit/byJob", response_model=AuditResponse)
async def audit_by_job(request: AuditByJobRequest):
    """Run audit on a previously completed job's generated DAML code."""
    data = _get_job_data(request.job_id)

    code = data.get("generated_code")
    if not code:
        raise HTTPException(status_code=400, detail="Job has no generated code to audit")

    if data.get("status") not in ("complete", "failed"):
        raise HTTPException(status_code=202, detail="Job still in progress")

    contract_name = "Contract"
    intent = data.get("structured_intent") or {}
    templates = intent.get("daml_templates_needed", [])
    if templates:
        contract_name = templates[0]

    result = run_hybrid_audit(
        daml_code=code,
        contract_name=contract_name,
        compliance_profile=request.compliance_profile,
        skip_compliance=request.skip_compliance,
        skip_audit=request.skip_audit,
    )

    combined = result.get("combined_scores", {})
    sec = result.get("security_audit") or {}
    comp = result.get("compliance_analysis") or {}

    return AuditResponse(
        success=result.get("success", False),
        security_score=combined.get("security_score"),
        compliance_score=combined.get("compliance_score"),
        enterprise_score=combined.get("enterprise_score"),
        enterprise_readiness=combined.get("enterprise_readiness"),
        deploy_gate=combined.get("deploy_gate"),
        executive_summary=sec.get("executive_summary"),
        compliance_summary=comp.get("executive_summary"),
        findings_count=sec.get("findings_count"),
        audit_report=sec.get("audit_report"),
        compliance_report=comp.get("compliance_report"),
        elapsed_seconds=result.get("elapsed_seconds"),
        error=result.get("error"),
    )


# ── Compliance Endpoints ─────────────────────────────────────────────────────

@audit_router.post("/compliance/analyze", response_model=ComplianceResponse)
async def compliance_analyze(request: ComplianceRequest):
    """Run compliance analysis on provided DAML code."""
    logger.info("API: compliance/analyze", profile=request.profile)

    result = run_compliance_analysis(
        daml_code=request.code,
        contract_name=request.contract_name,
        profile=request.profile,
    )

    return ComplianceResponse(
        success=result.get("success", False),
        compliance_score=result.get("compliance_score"),
        profile=result.get("profile"),
        executive_summary=result.get("executive_summary"),
        compliance_report=result.get("compliance_report"),
        error=result.get("error"),
    )


@audit_router.post("/compliance/byJob", response_model=ComplianceResponse)
async def compliance_by_job(request: ComplianceByJobRequest):
    """Run compliance check on a completed job's code."""
    data = _get_job_data(request.job_id)

    code = data.get("generated_code")
    if not code:
        raise HTTPException(status_code=400, detail="Job has no generated code")

    if data.get("status") not in ("complete", "failed"):
        raise HTTPException(status_code=202, detail="Job still in progress")

    contract_name = "Contract"
    intent = data.get("structured_intent") or {}
    templates = intent.get("daml_templates_needed", [])
    if templates:
        contract_name = templates[0]

    result = run_compliance_analysis(
        daml_code=code,
        contract_name=contract_name,
        profile=request.profile,
    )

    return ComplianceResponse(
        success=result.get("success", False),
        compliance_score=result.get("compliance_score"),
        profile=result.get("profile"),
        executive_summary=result.get("executive_summary"),
        compliance_report=result.get("compliance_report"),
        error=result.get("error"),
    )


# ── Report Endpoints ─────────────────────────────────────────────────────────

@audit_router.get("/audit/report/{job_id}", response_model=ReportResponse)
async def get_audit_report(job_id: str, format: str = "all"):
    """
    Get audit reports for a completed job.
    format: json | markdown | html | all
    """
    data = _get_job_data(job_id)

    # Check if audit was already run as part of pipeline
    reports = data.get("audit_reports", {})
    if reports:
        resp = ReportResponse(
            success=True,
            job_id=job_id,
            formats_available=[k for k in reports if reports[k]],
        )
        if format in ("json", "all") and reports.get("json"):
            resp.json_report = reports["json"]
        if format in ("markdown", "all") and reports.get("markdown"):
            resp.markdown_report = reports["markdown"]
        if format in ("html", "all") and reports.get("html"):
            resp.html_report = reports["html"]
        return resp

    # No cached reports — run audit now
    code = data.get("generated_code")
    if not code:
        raise HTTPException(status_code=400, detail="No code or reports available for this job")

    result = run_hybrid_audit(daml_code=code, contract_name="Contract")
    reports = result.get("reports", {})

    resp = ReportResponse(
        success=True,
        job_id=job_id,
        formats_available=[k for k in reports if reports[k]],
    )
    if format in ("json", "all"):
        resp.json_report = reports.get("json")
    if format in ("markdown", "all"):
        resp.markdown_report = reports.get("markdown")
    if format in ("html", "all"):
        resp.html_report = reports.get("html")
    return resp


@audit_router.get("/compliance/profiles")
async def list_compliance_profiles():
    """List available compliance profiles."""
    return {
        "profiles": sorted(VALID_PROFILES),
        "descriptions": {
            "nist-800-53": "NIST 800-53 Rev 5 — Federal/Government compliance",
            "soc2-type2": "SOC 2 Type II — SaaS/Enterprise trust criteria",
            "iso27001": "ISO 27001:2022 — International security management",
            "defi-security": "DeFi Security — Canton DLT attack vector coverage",
            "canton-dlt": "Canton DLT Standards — DAML best practices",
            "generic": "Generic Security — Baseline for all contracts",
        },
    }
