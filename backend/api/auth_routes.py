"""Authentication API routes for Ginie.

Endpoints:
  POST /auth/challenge   — Generate a challenge for Ed25519 signing.
  POST /auth/verify      — Verify signature only (does NOT register party).
  POST /auth/register    — Register party on Canton + issue JWT.
  GET  /auth/me          — Get current authenticated user info.
  POST /auth/refresh     — Refresh JWT expiry.
  POST /auth/logout      — Invalidate JWT (blocklist).
"""

import structlog
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from api.rate_limiter import limiter

from auth.crypto import generate_challenge, verify_signature, compute_fingerprint
from auth.jwt_manager import create_user_jwt, refresh_user_jwt, create_canton_jwt
from auth.party_manager import register_party, get_party, list_parties
from api.middleware import get_current_user, optional_auth, blocklist_token, _extract_token
from config import get_settings

logger = structlog.get_logger()
auth_router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChallengeResponse(BaseModel):
    challenge: str
    expires_in: int


class VerifyRequest(BaseModel):
    challenge: str = Field(..., min_length=16)
    signature: str = Field(..., description="Base64-encoded Ed25519 signature")
    public_key: str = Field(..., description="Base64-encoded Ed25519 public key")


class VerifyResponse(BaseModel):
    verified: bool
    fingerprint: Optional[str] = None


class RegisterRequest(BaseModel):
    public_key: str = Field(..., description="Base64-encoded Ed25519 public key")
    party_name: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")
    canton_url: Optional[str] = None


class RegisterResponse(BaseModel):
    token: str
    party_id: str
    display_name: str
    fingerprint: str
    expires_in_days: int


class MeResponse(BaseModel):
    party_id: str
    display_name: str
    fingerprint: str
    canton_env: Optional[str] = None
    registered_at: Optional[str] = None


class PartyListResponse(BaseModel):
    parties: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@auth_router.post("/challenge", response_model=ChallengeResponse)
@limiter.limit("10/minute")
async def create_challenge(request: Request):
    """Generate a random challenge for the client to sign with their Ed25519 key."""
    result = generate_challenge()
    return ChallengeResponse(**result)


@auth_router.post("/verify", response_model=VerifyResponse)
@limiter.limit("10/minute")
async def verify_challenge(request: Request, body: VerifyRequest = Depends()):
    """Verify an Ed25519 signature against the challenge.

    This ONLY verifies the signature — it does NOT register a party or issue a JWT.
    Separating verify from register means if Canton party allocation fails,
    the user doesn't need to re-sign the challenge.
    """
    ok = verify_signature(body.challenge, body.signature, body.public_key)
    if not ok:
        raise HTTPException(status_code=401, detail="Signature verification failed")

    fingerprint = compute_fingerprint(body.public_key)
    return VerifyResponse(verified=True, fingerprint=fingerprint)


@auth_router.post("/register", response_model=RegisterResponse)
@limiter.limit("10/minute")
async def register_and_authenticate(request: Request, body: RegisterRequest = Depends()):
    """Register a party on Canton and issue a JWT.

    The client should call /auth/verify first to confirm their key works,
    then call this endpoint to register the party and get a JWT.
    """
    settings = get_settings()
    fingerprint = compute_fingerprint(body.public_key)

    try:
        result = await register_party(
            party_name=body.party_name,
            fingerprint=fingerprint,
            canton_url=body.canton_url,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Party registration failed: {e}")

    token = create_user_jwt(
        party_id=result["party_id"],
        fingerprint=fingerprint,
        display_name=body.party_name,
    )

    return RegisterResponse(
        token=token,
        party_id=result["party_id"],
        display_name=body.party_name,
        fingerprint=fingerprint,
        expires_in_days=settings.jwt_expiry_days,
    )


@auth_router.get("/me", response_model=MeResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Return current authenticated user info from JWT + database."""
    party_id = user["sub"]
    party_record = get_party(party_id)

    return MeResponse(
        party_id=party_id,
        display_name=user.get("display_name", ""),
        fingerprint=user.get("fingerprint", ""),
        canton_env=party_record.get("canton_env") if party_record else None,
        registered_at=party_record.get("created_at") if party_record else None,
    )


@auth_router.post("/refresh")
async def refresh_token(user: dict = Depends(get_current_user)):
    """Refresh the JWT — extend expiry without re-authentication."""
    from fastapi import Request
    # We need the raw token to refresh it
    try:
        new_token = create_user_jwt(
            party_id=user["sub"],
            fingerprint=user.get("fingerprint", ""),
            display_name=user.get("display_name", ""),
        )
        settings = get_settings()
        return {
            "token": new_token,
            "expires_in_days": settings.jwt_expiry_days,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {e}")


@auth_router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Invalidate the current JWT by adding it to the Redis blocklist."""
    raw_token = user.get("_raw_token", "")
    if raw_token:
        blocklist_token(raw_token)
        logger.info("Token blocklisted", party_id=user.get("sub"))
    return {"status": "logged_out", "party_id": user.get("sub")}


@auth_router.get("/parties", response_model=PartyListResponse)
async def get_parties(user: dict = Depends(get_current_user)):
    """List all registered parties for the current environment."""
    settings = get_settings()
    parties = list_parties(canton_env=settings.canton_environment)
    return PartyListResponse(parties=parties)
