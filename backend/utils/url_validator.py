"""SSRF-safe URL validation for client-supplied Canton endpoint URLs.

Blocks requests to:
- Non-HTTP/HTTPS schemes
- Loopback addresses (unless explicitly allowed by the running environment)
- RFC-1918 private ranges
- Link-local / APIPA ranges
- Cloud metadata endpoints (AWS IMDSv1/v2, GCP, Azure)
- Unresolvable hostnames

Usage:
    from utils.url_validator import validate_canton_url

    safe_url = validate_canton_url(body.canton_url)  # raises ValueError on bad input
"""

import ipaddress
import re
import socket
import structlog
from urllib.parse import urlparse

logger = structlog.get_logger()

_ALLOWED_SCHEMES = {"http", "https"}

_METADATA_HOSTNAMES = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.goog",
}

_METADATA_PATTERN = re.compile(
    r"^(169\.254\.169\.254|fd00:ec2::254|"
    r"metadata\.google\.internal|metadata\.goog)$",
    re.IGNORECASE,
)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def validate_canton_url(raw_url: str, *, allow_localhost: bool = False) -> str:
    """Validate and return a safe Canton URL supplied by the client.

    Args:
        raw_url: The URL string provided by the API caller.
        allow_localhost: If True, loopback addresses are permitted
                         (sandbox development mode only — never production).

    Returns:
        The stripped, validated URL string.

    Raises:
        ValueError: With a human-readable message if the URL is unsafe.
    """
    if not raw_url or not raw_url.strip():
        raise ValueError("canton_url must not be empty")

    url = raw_url.strip()

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"Malformed URL: {exc}") from exc

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"canton_url scheme '{parsed.scheme}' is not allowed; use http or https"
        )

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("canton_url must include a hostname")

    if _METADATA_PATTERN.match(hostname):
        raise ValueError(
            f"canton_url hostname '{hostname}' is a cloud-metadata endpoint and is blocked"
        )

    try:
        resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        ip_strs = {r[4][0] for r in resolved}
    except socket.gaierror:
        raise ValueError(f"canton_url hostname '{hostname}' could not be resolved")

    for ip_str in ip_strs:
        if _METADATA_PATTERN.match(ip_str):
            raise ValueError(
                f"canton_url resolves to cloud-metadata IP '{ip_str}' — blocked"
            )
        if not allow_localhost and _is_private_ip(ip_str):
            raise ValueError(
                f"canton_url resolves to a private/internal IP '{ip_str}' — "
                "client-supplied URLs must point to public endpoints"
            )

    logger.debug("canton_url validated", url=url, resolved_ips=list(ip_strs))
    return url
