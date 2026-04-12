"""Authentication middleware for FastAPI — JWT extraction and verification.

Provides two dependency functions:
  - get_current_user(): Requires valid JWT, raises 401 if missing/invalid.
  - optional_auth(): Returns user context or None (unauthenticated mode still works).
"""

import structlog
import redis as redis_lib
from typing import Optional
from fastapi import HTTPException, Request

from config import get_settings
from auth.jwt_manager import verify_user_jwt

logger = structlog.get_logger()

# Redis key prefix for blocklisted (logged-out) tokens
_BLOCKLIST_PREFIX = "auth:blocklist:"


def _get_redis():
    settings = get_settings()
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


def _extract_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


def _is_token_blocklisted(token: str) -> bool:
    """Check if a token has been logged out (blocklisted in Redis)."""
    try:
        r = _get_redis()
        return r.exists(f"{_BLOCKLIST_PREFIX}{token}") > 0
    except Exception:
        return False


def blocklist_token(token: str, ttl_seconds: int = 604800) -> None:
    """Add a token to the blocklist (used by logout endpoint).

    Args:
        token: JWT string to blocklist.
        ttl_seconds: How long to keep in blocklist (default: 7 days).
    """
    try:
        r = _get_redis()
        r.set(f"{_BLOCKLIST_PREFIX}{token}", "1", ex=ttl_seconds)
    except Exception as e:
        logger.warning("Failed to blocklist token in Redis", error=str(e))


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency — requires authenticated user.

    Returns:
        Decoded JWT claims dict with keys: sub, party, fingerprint, display_name, etc.

    Raises:
        HTTPException 401: If no token, invalid token, or blocklisted token.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if _is_token_blocklisted(token):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        claims = verify_user_jwt(token)
        claims["_raw_token"] = token  # Pass raw token for logout/blocklist
        return claims
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")


async def optional_auth(request: Request) -> Optional[dict]:
    """FastAPI dependency — returns user context or None.

    This keeps unauthenticated mode working for users who skip the setup wizard.
    """
    token = _extract_token(request)
    if not token:
        return None

    if _is_token_blocklisted(token):
        return None

    try:
        return verify_user_jwt(token)
    except Exception:
        return None
