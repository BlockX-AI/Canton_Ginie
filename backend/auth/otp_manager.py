"""Email OTP (One-Time Password) manager for signup verification.

OTPs are 6-digit codes sent via Brevo. Codes are hashed (SHA-256) before
storage. Each code expires after N minutes and allows max N attempts.
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Tuple

import structlog

from db.session import get_db_session
from db.models import EmailOTP, EmailAccount
from services.brevo_service import send_otp_email
from config import get_settings

logger = structlog.get_logger()


def _generate_otp() -> str:
    """Generate a cryptographically-secure 6-digit OTP."""
    # Uniformly distributed 000000-999999
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp: str) -> str:
    """Hash OTP for secure storage."""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def send_otp(email: str, purpose: str = "signup", display_name: str = None) -> Tuple[bool, str]:
    """Generate and send an OTP to the given email.
    
    Returns (success, error_message).
    """
    settings = get_settings()
    email = _normalize_email(email)
    
    # Generate new OTP
    otp = _generate_otp()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.otp_expiry_minutes)
    
    # Store in DB (invalidate old unverified OTPs for the same email+purpose)
    try:
        with get_db_session() as session:
            session.query(EmailOTP).filter(
                EmailOTP.email == email,
                EmailOTP.purpose == purpose,
                EmailOTP.verified == 0,
            ).delete(synchronize_session=False)
            
            record = EmailOTP(
                email=email,
                otp_hash=_hash_otp(otp),
                purpose=purpose,
                created_at=now,
                expires_at=expires_at,
            )
            session.add(record)
    except Exception as e:
        logger.exception("Failed to persist OTP", email=email, error=str(e))
        return False, "Failed to generate OTP"
    
    # Send email via Brevo
    sent = await send_otp_email(email, otp, display_name=display_name)
    if not sent:
        logger.error("Failed to send OTP email", email=email)
        return False, "Failed to send verification email. Please try again."
    
    logger.info("OTP sent", email=email, purpose=purpose, expires_in_minutes=settings.otp_expiry_minutes)
    return True, ""


def verify_otp(email: str, otp: str, purpose: str = "signup") -> Tuple[bool, str]:
    """Verify an OTP code. Returns (success, error_message).
    
    On success, marks the OTP record as verified.
    """
    settings = get_settings()
    email = _normalize_email(email)
    
    if not otp or len(otp) != 6 or not otp.isdigit():
        return False, "OTP must be 6 digits"
    
    with get_db_session() as session:
        record = session.query(EmailOTP).filter(
            EmailOTP.email == email,
            EmailOTP.purpose == purpose,
            EmailOTP.verified == 0,
        ).order_by(EmailOTP.created_at.desc()).first()
        
        if not record:
            return False, "No active code found. Please request a new one."
        
        # Check attempts
        if record.attempts >= settings.otp_max_attempts:
            return False, "Too many incorrect attempts. Please request a new code."
        
        # Check expiry
        now = datetime.now(timezone.utc)
        # expires_at is timezone-aware from the DB (postgres TIMESTAMPTZ)
        exp = record.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return False, "Code expired. Please request a new one."
        
        # Increment attempts
        record.attempts += 1
        
        # Compare hash
        if _hash_otp(otp) != record.otp_hash:
            remaining = settings.otp_max_attempts - record.attempts
            if remaining <= 0:
                return False, "Too many incorrect attempts. Please request a new code."
            return False, f"Invalid code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
        
        # Success
        record.verified = 1
        record.verified_at = now
        
        # Also mark email_accounts.email_verified if account exists
        account = session.query(EmailAccount).filter(EmailAccount.email == email).first()
        if account:
            account.email_verified = 1
            account.email_verified_at = now
        
        logger.info("OTP verified", email=email, purpose=purpose)
        return True, ""


def is_email_verified_recently(email: str, window_minutes: int = 30) -> bool:
    """Check if email has a verified OTP within the given window.
    
    Used to gate signup: user must verify email before /signup endpoint.
    """
    email = _normalize_email(email)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    
    with get_db_session() as session:
        verified = session.query(EmailOTP).filter(
            EmailOTP.email == email,
            EmailOTP.purpose == "signup",
            EmailOTP.verified == 1,
            EmailOTP.verified_at >= cutoff,
        ).first()
        return verified is not None


def consume_signup_verification(email: str) -> bool:
    """Consume the signup verification after successful account creation.
    
    Marks the OTP record as consumed so it can't be reused.
    """
    email = _normalize_email(email)
    with get_db_session() as session:
        records = session.query(EmailOTP).filter(
            EmailOTP.email == email,
            EmailOTP.purpose == "signup",
            EmailOTP.verified == 1,
        ).all()
        for r in records:
            # Keep for audit trail but change purpose so is_email_verified_recently returns False
            r.purpose = "signup_consumed"
        return True
