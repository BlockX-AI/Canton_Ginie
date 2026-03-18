"""Ginie SDK configuration."""

from dataclasses import dataclass, field


@dataclass
class GinieConfig:
    """Configuration for the Ginie SDK client.

    Attributes:
        base_url: Base URL of the Ginie backend API.
        timeout: Default request timeout in seconds.
        poll_interval: Seconds between status polls when waiting for completion.
        poll_timeout: Maximum seconds to wait for job completion.
        canton_environment: Canton environment target (sandbox, devnet, mainnet).
        canton_url: Optional Canton JSON API URL override.
    """

    base_url: str = "http://localhost:8000/api/v1"
    timeout: int = 60
    poll_interval: float = 3.0
    poll_timeout: float = 300.0
    canton_environment: str = "sandbox"
    canton_url: str = ""
    headers: dict = field(default_factory=dict)
