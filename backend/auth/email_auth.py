"""Email/password authentication — layered on top of party identity.

The email account is the login credential; a party (Ed25519) is created
after signup and linked. Contracts are still owned by the party.
"""

from datetime import datetime, timezone
from typing import Optional

import bcrypt
import structlog

logger = structlog.get_logger()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with a per-password salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt verification."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_email_account(email: str, password: str, display_name: Optional[str] = None) -> dict:
    """Create a new email account. Raises ValueError if email already exists."""
    from db.session import get_db_session
    from db.models import EmailAccount

    email_norm = email.strip().lower()
    pw_hash = hash_password(password)

    with get_db_session() as session:
        existing = session.query(EmailAccount).filter_by(email=email_norm).first()
        if existing:
            raise ValueError("An account with this email already exists.")

        account = EmailAccount(
            email=email_norm,
            password_hash=pw_hash,
            display_name=display_name or email_norm.split("@")[0],
        )
        session.add(account)
        session.flush()
        result = {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "party_id": account.party_id,
        }

    logger.info("Email account created", email=email_norm)
    return result


def authenticate_email(email: str, password: str) -> Optional[dict]:
    """Return account dict if email + password match, else None."""
    from db.session import get_db_session
    from db.models import EmailAccount

    email_norm = email.strip().lower()

    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email_norm).first()
        if not account:
            return None
        if not verify_password(password, account.password_hash):
            return None

        account.last_login_at = datetime.now(timezone.utc)
        result = {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "party_id": account.party_id,
        }
    return result


def link_party_to_email(email: str, party_id: str, display_name: Optional[str] = None) -> dict:
    """Attach a party_id to an email account after the user creates a party."""
    from db.session import get_db_session
    from db.models import EmailAccount

    email_norm = email.strip().lower()

    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email_norm).first()
        if not account:
            raise ValueError("Email account not found.")
        account.party_id = party_id
        if display_name:
            account.display_name = display_name
        result = {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "party_id": account.party_id,
        }

    logger.info("Party linked to email account", email=email_norm, party_id=party_id)
    return result


def get_email_account(email: str) -> Optional[dict]:
    """Look up an email account by email address."""
    from db.session import get_db_session
    from db.models import EmailAccount

    email_norm = email.strip().lower()

    with get_db_session() as session:
        account = session.query(EmailAccount).filter_by(email=email_norm).first()
        if not account:
            return None
        return {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "party_id": account.party_id,
        }
