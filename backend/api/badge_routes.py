"""Badge endpoints.

  GET /badges               — List the badge catalog (public).
  GET /badges/me            — Get my earned badges.
"""

import structlog
from fastapi import APIRouter, HTTPException, Depends

from api.middleware import get_current_user
from services.badge_service import list_all_badges, get_user_badges, check_and_award_badges

logger = structlog.get_logger()
badge_router = APIRouter(prefix="/badges", tags=["badges"])


def _email_from_token(user: dict) -> str:
    sub = user.get("sub", "")
    if sub.startswith("email:"):
        return sub[len("email:"):]
    raise HTTPException(status_code=400, detail="Not an email account token")


@badge_router.get("")
async def list_badges():
    """Public endpoint: list all available badges in the catalog."""
    return {"badges": list_all_badges()}


@badge_router.get("/me")
async def my_badges(user: dict = Depends(get_current_user)):
    """Get the current user's earned badges."""
    email = _email_from_token(user)
    # Re-check criteria-based badges on fetch (cheap and self-healing)
    try:
        check_and_award_badges(email)
    except Exception:
        pass
    return {"badges": get_user_badges(email)}
