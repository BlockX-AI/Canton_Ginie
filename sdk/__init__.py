"""Ginie SDK — Programmatic access to AI-powered DAML contract generation, audit, and deployment."""

from sdk.client.ginie_client import GinieClient
from sdk.client.types import (
    JobStatus,
    JobResult,
    AuditReport,
    ComplianceReport,
    GinieAPIError,
    GinieTimeoutError,
)

__version__ = "0.1.0"
__all__ = [
    "GinieClient",
    "JobStatus",
    "JobResult",
    "AuditReport",
    "ComplianceReport",
    "GinieAPIError",
    "GinieTimeoutError",
]
