"""Invite code management for invite-only signup."""

import secrets
import string
import structlog
from datetime import datetime, timezone
from typing import Optional

logger = structlog.get_logger()


def generate_invite_code(length: int = 12) -> str:
    """Generate a random invite code in format GS-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(secrets.choice(chars) for _ in range(4))
    part2 = ''.join(secrets.choice(chars) for _ in range(4))
    return f"GS-{part1}-{part2}"


def create_invite_codes(count: int, created_by: Optional[str] = None, notes: Optional[str] = None) -> list[str]:
    """Generate multiple invite codes and store them in the database.
    
    Args:
        count: Number of invite codes to generate.
        created_by: Optional identifier of who created these codes.
        notes: Optional notes about this batch of codes.
        
    Returns:
        List of generated invite codes.
    """
    from db.session import get_db_session
    from db.models import InviteCode
    
    codes = []
    with get_db_session() as session:
        for _ in range(count):
            # Ensure uniqueness
            while True:
                code = generate_invite_code()
                existing = session.query(InviteCode).filter_by(code=code).first()
                if not existing:
                    break
            
            invite = InviteCode(
                code=code,
                created_by=created_by,
                notes=notes,
            )
            session.add(invite)
            codes.append(code)
        
        logger.info("Generated invite codes", count=count, created_by=created_by)
    
    return codes


def validate_invite_code(code: str) -> bool:
    """Check if an invite code exists and is unused.
    
    Args:
        code: The invite code to validate.
        
    Returns:
        True if code is valid and unused, False otherwise.
    """
    from db.session import get_db_session
    from db.models import InviteCode
    
    try:
        with get_db_session() as session:
            invite = session.query(InviteCode).filter_by(code=code).first()
            if not invite:
                logger.warning("Invite code not found", code=code[:8])
                return False
            
            if invite.used:
                logger.warning("Invite code already used", code=code[:8], used_by=invite.used_by_email)
                return False
            
            return True
    except Exception as e:
        logger.error("Failed to validate invite code", error=str(e))
        return False


def mark_invite_code_used(code: str, email: str) -> bool:
    """Mark an invite code as used by a specific email.
    
    Args:
        code: The invite code to mark as used.
        email: The email address that used this code.
        
    Returns:
        True if successfully marked, False otherwise.
    """
    from db.session import get_db_session
    from db.models import InviteCode
    
    try:
        with get_db_session() as session:
            invite = session.query(InviteCode).filter_by(code=code).first()
            if not invite:
                logger.error("Cannot mark non-existent invite code as used", code=code[:8])
                return False
            
            if invite.used:
                logger.warning("Invite code already marked as used", code=code[:8])
                return False
            
            invite.used = 1
            invite.used_by_email = email
            invite.used_at = datetime.now(timezone.utc)
            
            logger.info("Invite code marked as used", code=code[:8], email=email)
            return True
    except Exception as e:
        logger.error("Failed to mark invite code as used", error=str(e))
        return False


def get_invite_stats() -> dict:
    """Get statistics about invite codes.
    
    Returns:
        Dictionary with total, used, and available counts.
    """
    from db.session import get_db_session
    from db.models import InviteCode
    
    try:
        with get_db_session() as session:
            total = session.query(InviteCode).count()
            used = session.query(InviteCode).filter_by(used=1).count()
            available = total - used
            
            return {
                "total": total,
                "used": used,
                "available": available,
            }
    except Exception as e:
        logger.error("Failed to get invite stats", error=str(e))
        return {"total": 0, "used": 0, "available": 0}


def list_invite_codes(limit: int = 100, used: Optional[bool] = None) -> list[dict]:
    """List invite codes with optional filtering.
    
    Args:
        limit: Maximum number of codes to return.
        used: If True, return only used codes. If False, only unused. If None, return all.
        
    Returns:
        List of invite code dictionaries.
    """
    from db.session import get_db_session
    from db.models import InviteCode
    
    try:
        with get_db_session() as session:
            query = session.query(InviteCode)
            
            if used is not None:
                query = query.filter_by(used=1 if used else 0)
            
            invites = query.order_by(InviteCode.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "code": inv.code,
                    "used": bool(inv.used),
                    "used_by_email": inv.used_by_email,
                    "used_at": inv.used_at.isoformat() if inv.used_at else None,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    "created_by": inv.created_by,
                    "notes": inv.notes,
                }
                for inv in invites
            ]
    except Exception as e:
        logger.error("Failed to list invite codes", error=str(e))
        return []
