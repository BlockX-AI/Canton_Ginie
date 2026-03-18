"""Ginie SDK response types and exceptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GinieAPIError(Exception):
    """Raised when the Ginie API returns an error response."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class GinieTimeoutError(Exception):
    """Raised when a polling operation exceeds the configured timeout."""

    def __init__(self, job_id: str, elapsed: float):
        self.job_id = job_id
        self.elapsed = elapsed
        super().__init__(f"Timeout waiting for job {job_id} after {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Response Types
# ---------------------------------------------------------------------------

@dataclass
class JobStatus:
    """Status snapshot of a pipeline job."""

    job_id: str
    status: str  # queued | running | complete | failed
    current_step: str = ""
    progress: int = 0
    updated_at: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "JobStatus":
        return cls(
            job_id=data.get("job_id", ""),
            status=data.get("status", "unknown"),
            current_step=data.get("current_step", ""),
            progress=data.get("progress", 0),
            updated_at=data.get("updated_at"),
            error_message=data.get("error_message"),
        )

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_terminal(self) -> bool:
        return self.status in ("complete", "failed")


@dataclass
class AuditReport:
    """Security audit results."""

    success: bool = False
    security_score: Optional[int] = None
    compliance_score: Optional[int] = None
    enterprise_score: Optional[float] = None
    enterprise_readiness: Optional[str] = None
    deploy_gate: Optional[bool] = None
    executive_summary: Optional[Dict[str, Any]] = None
    compliance_summary: Optional[Dict[str, Any]] = None
    findings_count: Optional[int] = None
    audit_report: Optional[Dict[str, Any]] = None
    compliance_report: Optional[Dict[str, Any]] = None
    elapsed_seconds: Optional[float] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "AuditReport":
        return cls(
            success=data.get("success", False),
            security_score=data.get("security_score"),
            compliance_score=data.get("compliance_score"),
            enterprise_score=data.get("enterprise_score"),
            enterprise_readiness=data.get("enterprise_readiness"),
            deploy_gate=data.get("deploy_gate"),
            executive_summary=data.get("executive_summary"),
            compliance_summary=data.get("compliance_summary"),
            findings_count=data.get("findings_count"),
            audit_report=data.get("audit_report"),
            compliance_report=data.get("compliance_report"),
            elapsed_seconds=data.get("elapsed_seconds"),
            error=data.get("error"),
        )


@dataclass
class ComplianceReport:
    """Compliance analysis results."""

    success: bool = False
    compliance_score: Optional[int] = None
    profile: Optional[str] = None
    executive_summary: Optional[Dict[str, Any]] = None
    compliance_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ComplianceReport":
        return cls(
            success=data.get("success", False),
            compliance_score=data.get("compliance_score"),
            profile=data.get("profile"),
            executive_summary=data.get("executive_summary"),
            compliance_report=data.get("compliance_report"),
            error=data.get("error"),
        )


@dataclass
class JobResult:
    """Full result of a completed pipeline job."""

    job_id: str = ""
    status: str = ""
    success: Optional[bool] = None
    contract_id: Optional[str] = None
    package_id: Optional[str] = None
    template: Optional[str] = None
    template_id: Optional[str] = None
    fallback_used: Optional[bool] = None
    explorer_link: Optional[str] = None
    generated_code: Optional[str] = None
    structured_intent: Optional[Dict[str, Any]] = None
    attempt_number: Optional[int] = None
    error_message: Optional[str] = None
    compile_errors: Optional[List[Dict[str, Any]]] = None
    parties: Optional[Dict[str, str]] = None

    # Security & Compliance
    security_score: Optional[int] = None
    compliance_score: Optional[int] = None
    enterprise_score: Optional[float] = None
    deploy_gate: Optional[bool] = None
    audit_reports: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict) -> "JobResult":
        return cls(
            job_id=data.get("job_id", ""),
            status=data.get("status", ""),
            success=data.get("success"),
            contract_id=data.get("contract_id"),
            package_id=data.get("package_id"),
            template=data.get("template"),
            template_id=data.get("template_id"),
            fallback_used=data.get("fallback_used"),
            explorer_link=data.get("explorer_link"),
            generated_code=data.get("generated_code"),
            structured_intent=data.get("structured_intent"),
            attempt_number=data.get("attempt_number"),
            error_message=data.get("error_message"),
            compile_errors=data.get("compile_errors"),
            parties=data.get("parties"),
            security_score=data.get("security_score"),
            compliance_score=data.get("compliance_score"),
            enterprise_score=data.get("enterprise_score"),
            deploy_gate=data.get("deploy_gate"),
            audit_reports=data.get("audit_reports"),
        )

    @property
    def is_deployed(self) -> bool:
        return bool(self.contract_id)
