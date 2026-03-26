"""Party management — register, retrieve, and list persistent Canton parties.

Unlike the deploy agent's throwaway parties, parties created here are
persistent and tied to a user's Ed25519 key identity.
"""

import structlog
from datetime import datetime, timezone
from typing import Optional

from config import get_settings

logger = structlog.get_logger()


async def register_party(
    party_name: str,
    fingerprint: str,
    canton_url: Optional[str] = None,
) -> dict:
    """Register a new party on Canton and persist to PostgreSQL.

    Args:
        party_name: Display name / identifier hint for the party.
        fingerprint: Public key fingerprint (1220 + hex).
        canton_url: Override Canton URL (defaults to config).

    Returns:
        {"party_id": "...", "display_name": "...", "fingerprint": "..."}

    Raises:
        RuntimeError: If Canton party allocation fails.
    """
    settings = get_settings()
    url = canton_url or settings.get_canton_url()

    # Step 1: Allocate party on Canton ledger
    from canton.canton_client_v2 import CantonClientV2
    from auth.jwt_manager import create_canton_jwt

    token = create_canton_jwt([party_name])
    client = CantonClientV2(url, token)

    ok, party_id, err = await client.allocate_party(party_name)
    if not ok:
        raise RuntimeError(f"Canton party allocation failed for '{party_name}': {err}")

    logger.info("Party allocated on Canton", party_id=party_id, display_name=party_name)

    # Step 2: Persist to PostgreSQL
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty

        with get_db_session() as session:
            existing = session.query(RegisteredParty).filter_by(party_id=party_id).first()
            if existing:
                logger.info("Party already registered in DB", party_id=party_id)
            else:
                party = RegisteredParty(
                    party_id=party_id,
                    display_name=party_name,
                    public_key_fp=fingerprint,
                    canton_env=settings.canton_environment,
                )
                session.add(party)
                logger.info("Party persisted to PostgreSQL", party_id=party_id)
    except Exception as e:
        logger.warning("Failed to persist party to DB (Canton allocation succeeded)",
                       party_id=party_id, error=str(e))

    return {
        "party_id": party_id,
        "display_name": party_name,
        "fingerprint": fingerprint,
    }


def get_party(party_id: str) -> Optional[dict]:
    """Retrieve a registered party from PostgreSQL.

    Returns:
        Party dict or None if not found.
    """
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty

        with get_db_session() as session:
            party = session.query(RegisteredParty).filter_by(party_id=party_id).first()
            if party:
                return {
                    "party_id": party.party_id,
                    "display_name": party.display_name,
                    "fingerprint": party.public_key_fp,
                    "canton_env": party.canton_env,
                    "created_at": party.created_at.isoformat() if party.created_at else None,
                }
    except Exception as e:
        logger.warning("Failed to query party from DB", party_id=party_id, error=str(e))
    return None


def list_parties(canton_env: Optional[str] = None) -> list[dict]:
    """List all registered parties, optionally filtered by environment.

    Returns:
        List of party dicts.
    """
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty

        with get_db_session() as session:
            query = session.query(RegisteredParty)
            if canton_env:
                query = query.filter_by(canton_env=canton_env)
            parties = query.order_by(RegisteredParty.created_at.desc()).all()
            return [
                {
                    "party_id": p.party_id,
                    "display_name": p.display_name,
                    "fingerprint": p.public_key_fp,
                    "canton_env": p.canton_env,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in parties
            ]
    except Exception as e:
        logger.warning("Failed to list parties from DB", error=str(e))
    return []
