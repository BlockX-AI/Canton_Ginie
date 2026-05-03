"""Admin API routes for Ginie.

Endpoints:
  POST /admin/invite-codes/generate  — Generate new invite codes
  GET  /admin/invite-codes           — List invite codes
  GET  /admin/invite-codes/stats     — Get invite code statistics
"""

import structlog
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
from typing import Optional

from api.middleware import get_current_user
from config import get_settings

logger = structlog.get_logger()
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateInviteCodesRequest(BaseModel):
    count: int = Field(..., ge=1, le=1000, description="Number of invite codes to generate")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes about this batch")


class GenerateInviteCodesResponse(BaseModel):
    codes: list[str]
    count: int
    created_by: Optional[str]


class InviteCodeStatsResponse(BaseModel):
    total: int
    used: int
    available: int


class InviteCodeListResponse(BaseModel):
    codes: list[dict]
    count: int


class DeleteUserRequest(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# Admin middleware (simple check - can be enhanced with role-based auth)
# ---------------------------------------------------------------------------

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Verify user is an admin. For now, any authenticated user can access admin endpoints.
    
    TODO: Implement proper role-based access control.
    """
    # For now, allow any authenticated user to access admin endpoints
    # In production, check user role/permissions from database
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@admin_router.post("/invite-codes/generate", response_model=GenerateInviteCodesResponse)
async def generate_invite_codes(
    body: GenerateInviteCodesRequest,
    user: dict = Depends(require_admin),
):
    """Generate new invite codes.
    
    Requires admin authentication.
    """
    from auth.invite_manager import create_invite_codes
    
    try:
        created_by = user.get("sub", "unknown")
        codes = create_invite_codes(
            count=body.count,
            created_by=created_by,
            notes=body.notes,
        )
        
        logger.info("Generated invite codes via API", count=len(codes), created_by=created_by)
        
        return GenerateInviteCodesResponse(
            codes=codes,
            count=len(codes),
            created_by=created_by,
        )
    except Exception as e:
        logger.exception("Failed to generate invite codes", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate invite codes")


@admin_router.get("/invite-codes/stats", response_model=InviteCodeStatsResponse)
async def get_invite_code_stats(user: dict = Depends(require_admin)):
    """Get statistics about invite codes.
    
    Requires admin authentication.
    """
    from auth.invite_manager import get_invite_stats
    
    try:
        stats = get_invite_stats()
        return InviteCodeStatsResponse(**stats)
    except Exception as e:
        logger.exception("Failed to get invite code stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get invite code statistics")


@admin_router.get("/invite-codes", response_model=InviteCodeListResponse)
async def list_invite_codes(
    limit: int = Query(100, ge=1, le=1000),
    used: Optional[bool] = Query(None, description="Filter by used status"),
    user: dict = Depends(require_admin),
):
    """List invite codes with optional filtering.
    
    Requires admin authentication.
    """
    from auth.invite_manager import list_invite_codes as get_codes
    
    try:
        codes = get_codes(limit=limit, used=used)
        return InviteCodeListResponse(
            codes=codes,
            count=len(codes),
        )
    except Exception as e:
        logger.exception("Failed to list invite codes", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list invite codes")


# ---------------------------------------------------------------------------
# Analytics dashboard
# ---------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    password: str


def require_admin_password(x_admin_password: Optional[str] = Header(None)) -> None:
    """Gate analytics endpoints behind a shared admin password header.

    Kept separate from the JWT ``require_admin`` dependency because the
    analytics dashboard is intentionally password-only (no user JWT needed).
    """
    expected = (get_settings().admin_password or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin password not configured")
    if not x_admin_password or x_admin_password.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin password")


@admin_router.post("/login")
async def admin_login(body: AdminLoginRequest):
    """Verify the admin password. Returns success so the frontend can cache it."""
    expected = (get_settings().admin_password or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin password not configured")
    if (body.password or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"success": True}


# Range options for the timeline. Each entry: (window, bucket_seconds, num_buckets).
# bucket_seconds defines the granularity of each datapoint.
_RANGE_CONFIG: dict[str, tuple[timedelta, int, int]] = {
    "1h": (timedelta(hours=1), 60, 60),                    # 1 min buckets
    "6h": (timedelta(hours=6), 600, 36),                   # 10 min buckets
    "12h": (timedelta(hours=12), 1800, 24),                # 30 min buckets
    "1d": (timedelta(days=1), 3600, 24),                   # 1 hour buckets
    "7d": (timedelta(days=7), 3600 * 6, 28),               # 6 hour buckets
    "30d": (timedelta(days=30), 3600 * 24, 30),            # 1 day buckets
}


def _bucket_key(dt: datetime, bucket_seconds: int, anchor: datetime) -> int:
    """Map a timestamp to its bucket index relative to an anchor (the window start)."""
    delta = (dt - anchor).total_seconds()
    return int(delta // bucket_seconds)


@admin_router.get("/analytics")
async def get_analytics(
    range_: str = Query("30d", alias="range", description="Timeline window: 1h, 6h, 12h, 1d, 7d, 30d"),
    _: None = Depends(require_admin_password),
):
    """Aggregate platform analytics for the admin dashboard.

    Returns top-line counters, an activity timeline at the requested
    granularity, CC burn estimate (CC + USD), and most active users.
    """
    from db.session import get_db_session
    from db.models import (
        EmailAccount, RegisteredParty, JobHistory, DeployedContract, InviteCode
    )
    from sqlalchemy import func

    settings = get_settings()
    cc_per_contract = float(settings.cc_burn_per_contract or 0)
    usd_per_cc = float(settings.cc_to_usd_rate or 0)

    range_key = (range_ or "30d").lower()
    if range_key not in _RANGE_CONFIG:
        range_key = "30d"
    window, bucket_seconds, num_buckets = _RANGE_CONFIG[range_key]

    try:
        with get_db_session() as s:
            total_users = s.query(EmailAccount).count()
            verified_users = s.query(EmailAccount).filter(EmailAccount.email_verified == 1).count()
            total_parties = s.query(RegisteredParty).count()
            total_deployed = s.query(DeployedContract).count()
            total_jobs = s.query(JobHistory).count()
            successful_jobs = s.query(JobHistory).filter(JobHistory.status == "complete").count()
            failed_jobs = s.query(JobHistory).filter(JobHistory.status == "failed").count()
            invite_total = s.query(InviteCode).count()
            invite_used = s.query(InviteCode).filter(InviteCode.used == 1).count()

            # --- Timeline (range-aware) -----------------------------------
            now = datetime.now(timezone.utc)
            # Anchor the window so the *last* bucket ends at `now`.
            anchor = now - timedelta(seconds=bucket_seconds * num_buckets)

            users_rows = (
                s.query(EmailAccount.created_at)
                .filter(EmailAccount.created_at >= anchor)
                .all()
            )
            contracts_rows = (
                s.query(DeployedContract.created_at)
                .filter(DeployedContract.created_at >= anchor)
                .all()
            )
            jobs_rows = (
                s.query(JobHistory.created_at, JobHistory.status)
                .filter(JobHistory.created_at >= anchor)
                .all()
            )

            buckets: list[dict[str, int]] = [
                {"users": 0, "contracts": 0, "jobs": 0, "successful": 0}
                for _ in range(num_buckets)
            ]

            def _add(idx: int, key: str) -> None:
                if 0 <= idx < num_buckets:
                    buckets[idx][key] += 1

            for row in users_rows:
                if row.created_at:
                    _add(_bucket_key(row.created_at, bucket_seconds, anchor), "users")
            for row in contracts_rows:
                if row.created_at:
                    _add(_bucket_key(row.created_at, bucket_seconds, anchor), "contracts")
            for row in jobs_rows:
                if row.created_at:
                    idx = _bucket_key(row.created_at, bucket_seconds, anchor)
                    _add(idx, "jobs")
                    if row.status == "complete":
                        _add(idx, "successful")

            timeline = []
            for i in range(num_buckets):
                bucket_start = anchor + timedelta(seconds=bucket_seconds * i)
                timeline.append({
                    "date": bucket_start.isoformat(),
                    "users": buckets[i]["users"],
                    "contracts": buckets[i]["contracts"],
                    "jobs": buckets[i]["jobs"],
                    "successful": buckets[i]["successful"],
                })

            # --- Most active users ---------------------------------------
            deploy_counts = (
                s.query(DeployedContract.user_email, func.count(DeployedContract.id))
                .filter(DeployedContract.user_email.isnot(None))
                .group_by(DeployedContract.user_email)
                .order_by(func.count(DeployedContract.id).desc())
                .limit(10)
                .all()
            )
            job_counts = (
                s.query(JobHistory.user_email, func.count(JobHistory.id))
                .filter(
                    JobHistory.user_email.isnot(None),
                    JobHistory.status == "complete",
                )
                .group_by(JobHistory.user_email)
                .order_by(func.count(JobHistory.id).desc())
                .limit(10)
                .all()
            )

            active_map: dict[str, dict] = {}
            for email, cnt in deploy_counts:
                active_map.setdefault(email, {"email": email, "contracts": 0, "deploys": 0})
                active_map[email]["deploys"] = int(cnt)
            for email, cnt in job_counts:
                active_map.setdefault(email, {"email": email, "contracts": 0, "deploys": 0})
                active_map[email]["contracts"] = int(cnt)

            # Attach display name + xp where we have it
            if active_map:
                accts = (
                    s.query(EmailAccount.email, EmailAccount.display_name, EmailAccount.xp)
                    .filter(EmailAccount.email.in_(list(active_map.keys())))
                    .all()
                )
                for email, name, xp in accts:
                    if email in active_map:
                        active_map[email]["display_name"] = name or email.split("@")[0]
                        active_map[email]["xp"] = int(xp or 0)

            most_active = sorted(
                active_map.values(),
                key=lambda x: (x.get("deploys", 0), x.get("contracts", 0)),
                reverse=True,
            )[:10]

            # --- Canton env breakdown -------------------------------------
            env_rows = (
                s.query(DeployedContract.canton_env, func.count(DeployedContract.id))
                .group_by(DeployedContract.canton_env)
                .all()
            )
            env_breakdown = [
                {"env": env or "unknown", "count": int(cnt)} for env, cnt in env_rows
            ]

            # --- Template popularity --------------------------------------
            template_rows = (
                s.query(DeployedContract.template_id, func.count(DeployedContract.id))
                .filter(DeployedContract.template_id.isnot(None), DeployedContract.template_id != "")
                .group_by(DeployedContract.template_id)
                .order_by(func.count(DeployedContract.id).desc())
                .limit(8)
                .all()
            )
            top_templates = [
                {"template": (t.split(":")[-1] if t else "unknown"), "count": int(c)}
                for t, c in template_rows
            ]

            # --- Job status distribution ----------------------------------
            status_rows = (
                s.query(JobHistory.status, func.count(JobHistory.id))
                .filter(JobHistory.status != "failed")
                .group_by(JobHistory.status)
                .all()
            )
            status_breakdown = [{"status": st or "unknown", "count": int(c)} for st, c in status_rows]

        # Derived metrics (outside the session)
        non_failed_jobs = max(total_jobs - failed_jobs, 0)
        success_rate = round(100 * successful_jobs / non_failed_jobs, 1) if non_failed_jobs else 0.0
        estimated_cc_burn = round(total_deployed * cc_per_contract, 2)
        estimated_usd_value = round(estimated_cc_burn * usd_per_cc, 2)

        return {
            "totals": {
                "users": total_users,
                "verified_users": verified_users,
                "parties": total_parties,
                "deployed_contracts": total_deployed,
                "total_jobs": non_failed_jobs,
                "successful_jobs": successful_jobs,
                "success_rate": success_rate,
                "invite_codes_total": invite_total,
                "invite_codes_used": invite_used,
                "estimated_cc_burn": estimated_cc_burn,
                "cc_burn_per_contract": cc_per_contract,
                "estimated_usd_value": estimated_usd_value,
                "cc_to_usd_rate": usd_per_cc,
            },
            "range": range_key,
            "bucket_seconds": bucket_seconds,
            "timeline": timeline,
            "most_active_users": most_active,
            "env_breakdown": env_breakdown,
            "top_templates": top_templates,
            "status_breakdown": status_breakdown,
            "generated_at": now.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to compute analytics")


@admin_router.delete("/users")
async def delete_user(body: DeleteUserRequest):
    """Delete a user account by email.
    
    TEMPORARY: No auth required for testing.
    """
    from db.session import get_db_session
    from db.models import EmailAccount
    
    try:
        with get_db_session() as db:
            account = db.query(EmailAccount).filter(EmailAccount.email == body.email).first()
            if not account:
                raise HTTPException(status_code=404, detail="Account not found")
            db.delete(account)
            db.commit()
            logger.info("Deleted account via admin API", email=body.email)
            return {"success": True, "message": f"Account {body.email} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete account", email=body.email, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete account")
