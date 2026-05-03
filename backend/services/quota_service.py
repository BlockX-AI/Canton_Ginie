"""Per-user contract generation quota.

Counts ``JobHistory`` rows with ``status="complete"`` for a user (matched by
``user_email``) and compares to ``settings.contract_generation_limit``.

A comma-separated allowlist (``contract_limit_bypass_emails``) lets internal
accounts bypass the cap. ``"*"`` disables the cap globally.
"""

from __future__ import annotations

from typing import Optional, TypedDict

import structlog

from config import get_settings
from db.session import get_db_session
from db.models import JobHistory

logger = structlog.get_logger()


class Quota(TypedDict):
    used: int
    limit: int
    remaining: int
    can_generate: bool
    bypass: bool


def _bypass_set() -> set[str]:
    raw = (get_settings().contract_limit_bypass_emails or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_bypassed(email: Optional[str]) -> bool:
    raw = (get_settings().contract_limit_bypass_emails or "").strip()
    if raw == "*":
        return True
    if not email:
        return False
    return email.strip().lower() in _bypass_set()


def get_quota(email: Optional[str]) -> Quota:
    """Return quota status for a user.

    Anonymous users (no email) get a permissive quota — the per-IP rate
    limiter on ``/generate`` already bounds them. The lifetime cap only
    applies to authenticated email accounts.
    """
    settings = get_settings()
    limit = int(settings.contract_generation_limit or 0)

    # No email = anonymous; can_generate always true (rate limiter handles it).
    if not email:
        return Quota(used=0, limit=limit, remaining=limit, can_generate=True, bypass=False)

    if _is_bypassed(email):
        return Quota(used=0, limit=limit, remaining=limit, can_generate=True, bypass=True)

    used = 0
    try:
        with get_db_session() as session:
            used = (
                session.query(JobHistory)
                .filter(
                    JobHistory.user_email == email,
                    JobHistory.status == "complete",
                )
                .count()
            )
    except Exception as e:
        logger.warning("Quota lookup failed; defaulting to 0", email=email, error=str(e))
        used = 0

    remaining = max(limit - used, 0)
    can_generate = limit <= 0 or used < limit
    return Quota(
        used=used,
        limit=limit,
        remaining=remaining,
        can_generate=can_generate,
        bypass=False,
    )


def is_over_limit(email: Optional[str]) -> bool:
    q = get_quota(email)
    return not q["can_generate"]
