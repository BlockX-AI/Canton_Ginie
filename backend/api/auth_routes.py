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
from fastapi import APIRouter, HTTPException, Depends, Request, Body
from pydantic import BaseModel, Field
from typing import Optional

from api.rate_limiter import limiter

from auth.crypto import generate_challenge, verify_signature, compute_fingerprint
from auth.jwt_manager import create_user_jwt
from auth.party_manager import register_party, get_party, get_party_by_fingerprint, list_parties
from auth.email_auth import (
    create_email_account,
    authenticate_email,
    link_party_to_email,
    get_email_account,
)
from api.middleware import get_current_user, blocklist_token
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


class LoginRequest(BaseModel):
    challenge: str = Field(..., min_length=16)
    signature: str = Field(..., description="Base64-encoded Ed25519 signature")
    public_key: str = Field(..., description="Base64-encoded Ed25519 public key")


class LoginResponse(BaseModel):
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
async def verify_challenge(request: Request, body: VerifyRequest = Body()):
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
async def register_and_authenticate(request: Request, body: RegisterRequest = Body()):
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


@auth_router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login_existing_party(request: Request, body: LoginRequest = Body()):
    """Session recovery for an existing party.

    Flow:
      1. Verify the Ed25519 signature against the challenge.
      2. Compute fingerprint from the public key.
      3. Look up the party in PostgreSQL by fingerprint (no Canton call).
      4. Issue a fresh JWT for the existing party.

    This endpoint does NOT allocate a new party on Canton — it only recovers
    a session for a party that was previously registered. Canton party
    allocation is permanent and one-way, so there is no "re-registration."

    Errors:
        401 — Signature verification failed.
        404 — No party found for this key (party_not_found=true in detail).
              Frontend should prompt the user to register a new party
              (e.g. Canton DB was reset, losing the allocation).
    """
    settings = get_settings()

    # Step 1: Verify signature (consumes the challenge atomically)
    ok = verify_signature(body.challenge, body.signature, body.public_key)
    if not ok:
        raise HTTPException(status_code=401, detail="Signature verification failed")

    # Step 2: Compute fingerprint
    fingerprint = compute_fingerprint(body.public_key)

    # Step 3: Look up party by fingerprint in current environment
    party = get_party_by_fingerprint(fingerprint, canton_env=settings.canton_environment)
    if not party:
        logger.info("Login failed — party not found for fingerprint",
                    fingerprint=fingerprint[:16], env=settings.canton_environment)
        raise HTTPException(
            status_code=404,
            detail={
                "party_not_found": True,
                "message": (
                    "No party is registered for this key on the current environment. "
                    "The Canton node may have been reset. Please register a new party."
                ),
                "environment": settings.canton_environment,
            },
        )

    # Step 4: Issue fresh JWT
    token = create_user_jwt(
        party_id=party["party_id"],
        fingerprint=fingerprint,
        display_name=party["display_name"],
    )

    logger.info("Session recovered for existing party",
                party_id=party["party_id"], display_name=party["display_name"])

    return LoginResponse(
        token=token,
        party_id=party["party_id"],
        display_name=party["display_name"],
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


# ---------------------------------------------------------------------------
# Email / password authentication (layered on top of party identity)
# ---------------------------------------------------------------------------

class EmailSignupRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=200)
    display_name: Optional[str] = Field(None, max_length=60)
    invite_code: str = Field(..., min_length=10, max_length=20, description="Invite code required for signup")


class EmailLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=200)


class EmailAuthResponse(BaseModel):
    token: str
    email: str
    display_name: Optional[str]
    party_id: Optional[str]
    party_name: Optional[str] = None
    needs_party: bool
    expires_in_days: int


class LinkPartyRequest(BaseModel):
    party_id: str = Field(..., min_length=4)
    display_name: Optional[str] = None


def _create_email_token(email: str, display_name: str, party_id: Optional[str]) -> str:
    """Issue a JWT for an email account. If party is linked, JWT also acts as
    a party JWT; otherwise it carries an empty party claim until linked."""
    return create_user_jwt(
        party_id=party_id or f"email:{email}",
        fingerprint=f"email:{email}",
        display_name=display_name or email.split("@")[0],
    )


@auth_router.post("/email/signup", response_model=EmailAuthResponse)
@limiter.limit("5/minute")
async def email_signup(request: Request, body: EmailSignupRequest = Body()):
    """Create a new email/password account. Party is created later via /setup.
    
    Requires a valid invite code for signup.
    """
    from auth.invite_manager import validate_invite_code, mark_invite_code_used
    
    settings = get_settings()
    
    # Validate invite code
    if not validate_invite_code(body.invite_code):
        raise HTTPException(
            status_code=403,
            detail="Invalid or already used invite code"
        )
    
    try:
        account = create_email_account(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
        
        # Mark invite code as used
        mark_invite_code_used(body.invite_code, body.email)
        
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("Email signup failed", error=str(e))
        raise HTTPException(status_code=500, detail="Signup failed")

    token = _create_email_token(
        email=account["email"],
        display_name=account["display_name"] or "",
        party_id=account.get("party_id"),
    )

    return EmailAuthResponse(
        token=token,
        email=account["email"],
        display_name=account["display_name"],
        party_id=None,
        party_name=None,
        needs_party=True,
        expires_in_days=settings.jwt_expiry_days,
    )


@auth_router.post("/email/login", response_model=EmailAuthResponse)
@limiter.limit("10/minute")
async def email_login(request: Request, body: EmailLoginRequest = Body()):
    """Authenticate an email/password pair and return a JWT."""
    settings = get_settings()
    account = authenticate_email(email=body.email, password=body.password)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Force party re-creation every session: ignore any previously-linked party
    # so each login lands the user back on the party-creation wizard. This avoids
    # `UNKNOWN_SUBMITTERS` errors when the Canton sandbox has lost the party.
    display_name = account["display_name"]
    if account.get("party_name") and display_name == account["party_name"]:
        # Stale overwrite from a previous link-party bug — recover the username
        # from the email local-part.
        display_name = account["email"].split("@")[0]

    token = _create_email_token(
        email=account["email"],
        display_name=display_name or "",
        party_id=None,
    )

    return EmailAuthResponse(
        token=token,
        email=account["email"],
        display_name=display_name,
        party_id=None,
        party_name=None,
        needs_party=True,
        expires_in_days=settings.jwt_expiry_days,
    )


@auth_router.post("/email/link-party", response_model=EmailAuthResponse)
async def email_link_party(
    body: LinkPartyRequest = Body(),
    user: dict = Depends(get_current_user),
):
    """Link a freshly created party to the authenticated email account."""
    settings = get_settings()
    sub = user.get("sub", "")
    if not sub.startswith("email:"):
        raise HTTPException(status_code=400, detail="Token is not an email-account token")

    email = sub[len("email:"):]
    try:
        account = link_party_to_email(
            email=email,
            party_id=body.party_id,
            display_name=body.display_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    token = _create_email_token(
        email=account["email"],
        display_name=account["display_name"] or "",
        party_id=account.get("party_id"),
    )

    return EmailAuthResponse(
        token=token,
        email=account["email"],
        display_name=account["display_name"],
        party_id=account.get("party_id"),
        party_name=account.get("party_name"),
        needs_party=False,
        expires_in_days=settings.jwt_expiry_days,
    )
