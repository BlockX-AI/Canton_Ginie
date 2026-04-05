"""Rate limiting configuration for Ginie API.

Uses slowapi with in-memory backend (falls back gracefully).
Limits:
  - /generate: 5 req/min per IP
  - /auth/*: 10 req/min per IP
  - /iterate: 10 req/min per IP
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Return 429 with Retry-After header on rate limit exceeded."""
    retry_after = getattr(exc, "retry_after", 60)
    logger.warning(
        "Rate limit exceeded",
        path=request.url.path,
        client=get_remote_address(request),
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
