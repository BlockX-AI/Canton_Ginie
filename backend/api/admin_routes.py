"""Admin API routes for Ginie.

Endpoints:
  POST /admin/invite-codes/generate  — Generate new invite codes
  GET  /admin/invite-codes           — List invite codes
  GET  /admin/invite-codes/stats     — Get invite code statistics
"""

import structlog
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

from api.middleware import get_current_user

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
