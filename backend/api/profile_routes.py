"""Profile management endpoints.

Endpoints:
  POST /profile/upload-picture      — Upload/update profile picture
  POST /profile/upload-picture-unauth — Upload during signup (pre-auth)
  GET  /profile/me                  — Get current user's profile with stats
  GET  /profile/user/{email}        — Get public user profile (badges, stats)
"""

import structlog
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from typing import Optional

from api.middleware import get_current_user
from api.rate_limiter import limiter
from services.cloudinary_service import (
    upload_profile_picture,
    validate_image,
    delete_profile_picture,
    is_cloudinary_configured,
    MAX_FILE_SIZE_BYTES,
)
from services.badge_service import get_user_badges, get_user_stats
from db.session import get_db_session
from db.models import EmailAccount

logger = structlog.get_logger()
profile_router = APIRouter(prefix="/profile", tags=["profile"])


def _email_from_token(user: dict) -> str:
    """Resolve the email account associated with the authenticated user.

    The JWT 'sub' is the Canton party_id. Email is stored on the EmailAccount
    row keyed by party_id.
    """
    sub = user.get("sub", "")
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid token")
    # Backward-compat: if sub is "email:xxx", strip prefix
    if sub.startswith("email:"):
        return sub[len("email:"):]
    # Otherwise sub is a party_id — look up the linked EmailAccount
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(party_id=sub).first()
        if not account:
            raise HTTPException(status_code=404, detail="No email account linked to this party")
        return account.email


@profile_router.post("/upload-picture")
@limiter.limit("10/minute")
async def upload_my_picture(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload or replace the current user's profile picture."""
    if not is_cloudinary_configured():
        raise HTTPException(status_code=503, detail="Image uploads are not configured on the server")
    
    email = _email_from_token(user)
    content = await file.read()
    
    valid, err = validate_image(content, file.content_type or "")
    if not valid:
        raise HTTPException(status_code=400, detail=err)
    
    # Get existing picture public_id to delete after upload
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        old_public_id = account.profile_picture_public_id
    
    url, public_id, err = upload_profile_picture(content, email, old_public_id=old_public_id)
    if err:
        raise HTTPException(status_code=500, detail=err)
    
    # Update DB
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email).first()
        if account:
            account.profile_picture_url = url
            account.profile_picture_public_id = public_id
    
    return {"profile_picture_url": url}


@profile_router.post("/upload-picture-signup")
@limiter.limit("10/minute")
async def upload_picture_signup(
    request: Request,
    email: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a profile picture during signup (before auth token exists).
    
    Requires the email to have a verified OTP within the last 30 minutes.
    """
    from auth.otp_manager import is_email_verified_recently
    
    if not is_cloudinary_configured():
        raise HTTPException(status_code=503, detail="Image uploads are not configured on the server")
    
    # Security: only allow upload if email has verified OTP recently
    if not is_email_verified_recently(email, window_minutes=30):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email first before uploading a picture."
        )
    
    content = await file.read()
    valid, err = validate_image(content, file.content_type or "")
    if not valid:
        raise HTTPException(status_code=400, detail=err)
    
    url, public_id, err = upload_profile_picture(content, email)
    if err:
        raise HTTPException(status_code=500, detail=err)
    
    # Stash the URL/public_id on any existing EmailAccount row; if the
    # account doesn't exist yet, return the URL for the client to send
    # along with the signup request.
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email.lower().strip()).first()
        if account:
            account.profile_picture_url = url
            account.profile_picture_public_id = public_id
    
    return {"profile_picture_url": url, "public_id": public_id}


@profile_router.delete("/picture")
async def delete_my_picture(user: dict = Depends(get_current_user)):
    """Remove the current user's profile picture."""
    email = _email_from_token(user)
    
    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        public_id = account.profile_picture_public_id
        account.profile_picture_url = None
        account.profile_picture_public_id = None
    
    if public_id:
        delete_profile_picture(public_id)
    
    return {"success": True}


@profile_router.get("/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """Get the current user's full profile with stats and badges."""
    email = _email_from_token(user)
    stats = get_user_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    badges = get_user_badges(email)
    return {**stats, "badges": badges}


@profile_router.get("/user/{email}")
async def get_public_profile(email: str):
    """Get a public user profile (no auth required)."""
    stats = get_user_stats(email)
    if not stats:
        raise HTTPException(status_code=404, detail="User not found")
    
    badges = get_user_badges(email)
    # Public profile: don't expose email
    return {
        "display_name": stats.get("display_name"),
        "profile_picture_url": stats.get("profile_picture_url"),
        "xp": stats.get("xp", 0),
        "level": stats.get("level", 1),
        "badge_count": stats.get("badge_count", 0),
        "contract_count": stats.get("contract_count", 0),
        "deploy_count": stats.get("deploy_count", 0),
        "member_since": stats.get("member_since"),
        "badges": badges,
    }
