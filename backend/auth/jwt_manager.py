"""JWT token management for Ginie authentication.

Two JWT types:
  - User JWT: HS256-signed, for Ginie API authentication.
  - Canton JWT: Unsigned wildcard JWT for Canton sandbox ledger operations.
"""

import jwt
import structlog
from datetime import datetime, timezone, timedelta

from config import get_settings

logger = structlog.get_logger()


def create_user_jwt(party_id: str, fingerprint: str, display_name: str = "") -> str:
    """Create a signed user JWT for Ginie API authentication.

    Args:
        party_id: Full Canton party ID (e.g., "alice::1220abc...").
        fingerprint: Public key fingerprint.
        display_name: Human-readable party name.

    Returns:
        Signed JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": party_id,
        "party": [party_id],
        "fingerprint": fingerprint,
        "display_name": display_name,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expiry_days),
        "iss": "ginie-daml",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_user_jwt(token: str) -> dict:
    """Verify and decode a user JWT.

    Args:
        token: JWT string.

    Returns:
        Decoded claims dict.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.InvalidTokenError: If token is invalid.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer="ginie-daml",
    )


def refresh_user_jwt(token: str) -> str:
    """Refresh a user JWT — extend expiry without re-authentication.

    Args:
        token: Current valid JWT string.

    Returns:
        New JWT string with extended expiry.

    Raises:
        jwt.InvalidTokenError: If current token is invalid.
    """
    claims = verify_user_jwt(token)
    return create_user_jwt(
        party_id=claims["sub"],
        fingerprint=claims["fingerprint"],
        display_name=claims.get("display_name", ""),
    )


def create_canton_jwt(party_ids: list[str]) -> str:
    """Create a Canton-compatible unsigned JWT for sandbox ledger operations.

    This wraps the existing make_sandbox_jwt() for consistency.

    Args:
        party_ids: List of party IDs to include in actAs/readAs.

    Returns:
        Unsigned JWT string accepted by Canton wildcard auth.
    """
    from canton.canton_client_v2 import make_sandbox_jwt
    return make_sandbox_jwt(party_ids)
