"""Party management — register, retrieve, and list persistent Canton parties.

Unlike the deploy agent's throwaway parties, parties created here are
persistent and tied to a user's Ed25519 key identity.
"""

import structlog
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


def get_party_by_fingerprint(fingerprint: str, canton_env: Optional[str] = None) -> Optional[dict]:
    """Retrieve a registered party by its public-key fingerprint.

    Used for session recovery — a returning user presents their key file,
    and we look up the party they previously allocated on Canton.

    Args:
        fingerprint: Public-key fingerprint (e.g. "1220abc...").
        canton_env: Optional filter by environment; if provided only parties
                    in that environment are returned.

    Returns:
        Party dict or None if not found.
    """
    try:
        from db.session import get_db_session
        from db.models import RegisteredParty

        with get_db_session() as session:
            query = session.query(RegisteredParty).filter_by(public_key_fp=fingerprint)
            if canton_env:
                query = query.filter_by(canton_env=canton_env)
            party = query.order_by(RegisteredParty.created_at.desc()).first()
            if party:
                return {
                    "party_id": party.party_id,
                    "display_name": party.display_name,
                    "fingerprint": party.public_key_fp,
                    "canton_env": party.canton_env,
                    "created_at": party.created_at.isoformat() if party.created_at else None,
                }
    except Exception as e:
        logger.warning("Failed to query party by fingerprint", fingerprint=fingerprint[:16], error=str(e))
    return None


def record_deploy_parties(
    parties: dict[str, str],
    user_email: Optional[str],
    canton_env: Optional[str] = None,
) -> int:
    """Persist every party allocated during a deploy to ``registered_parties``
    and stamp the owning user's email so ``/me/parties`` can surface them
    directly.

    Idempotent: if a row for ``party_id`` already exists we only patch in
    ``user_email`` / ``display_name`` when the existing value is empty.

    Args:
        parties: Mapping of ``role -> party_id`` as returned by
                 ``run_deploy_agent`` in its ``parties`` field.
        user_email: Authenticated user's email, or None for anonymous deploys
                    (nothing is written in that case).
        canton_env: Override the environment tag; defaults to the configured
                    ``canton_environment``.

    Returns:
        Number of rows created or updated. Never raises — any DB failure is
        swallowed and logged, because losing party bookkeeping must not break
        a successful contract deploy.
    """
    if not parties or not user_email:
        return 0

    settings = get_settings()
    env = canton_env or settings.canton_environment
    written = 0

    try:
        from db.session import get_db_session
        from db.models import RegisteredParty

        with get_db_session() as session:
            for role, party_id in parties.items():
                if not isinstance(party_id, str) or not party_id:
                    continue
                existing = (
                    session.query(RegisteredParty)
                    .filter_by(party_id=party_id)
                    .first()
                )
                if existing:
                    # Only fill in gaps \u2014 never clobber a pre-existing owner
                    # or display name. Keeps registrations done through
                    # /auth/register authoritative.
                    if not existing.user_email:
                        existing.user_email = user_email
                        written += 1
                    if not existing.display_name and isinstance(role, str):
                        existing.display_name = role
                else:
                    session.add(
                        RegisteredParty(
                            party_id=party_id,
                            display_name=str(role or party_id.split("::", 1)[0]),
                            canton_env=env,
                            user_email=user_email,
                        )
                    )
                    written += 1
    except Exception as e:
        logger.warning(
            "record_deploy_parties failed",
            user_email=user_email,
            error=str(e),
        )
        return 0

    logger.info(
        "Recorded deploy parties for user",
        user_email=user_email,
        count=written,
        parties=list(parties.keys()),
    )
    return written


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
