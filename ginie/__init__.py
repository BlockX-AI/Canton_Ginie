"""canton-ginie — Python SDK for AI-powered Canton smart contract generation.

This is a thin namespace shim that re-exports the public API from the
underlying `sdk` package so that users can simply write:

    from ginie import GinieClient

    client = GinieClient(base_url="https://api.ginie.xyz/api/v1")
    result = client.full_pipeline("Create a bond between issuer and investor")
    print(result.contract_id)

See https://github.com/BlockX-AI/Canton_Ginie for full docs.
"""

from sdk.client.ginie_client import GinieClient
from sdk.client.config import GinieConfig
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
    "GinieConfig",
    "JobStatus",
    "JobResult",
    "AuditReport",
    "ComplianceReport",
    "GinieAPIError",
    "GinieTimeoutError",
]
