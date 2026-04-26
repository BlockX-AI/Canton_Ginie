"""Database session factory for Ginie application.

Usage:
    from db.session import get_db_session, get_engine

    # In async context (FastAPI dependency):
    with get_db_session() as session:
        session.query(JobHistory).filter_by(job_id=job_id).first()

    # Create tables (startup):
    from db.models import Base
    Base.metadata.create_all(get_engine())
"""

import structlog
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import get_settings

logger = structlog.get_logger()

_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
        logger.info("Database engine created", url=settings.database_url.split("@")[-1])
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create the session factory (singleton)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_db_session():
    """Context manager for database sessions with auto-commit/rollback."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables if they don't exist.

    Guarded by INIT_DB_TABLES env var to avoid conflicts with Alembic.
    Defaults to "true" for sandbox/dev convenience.
    In production, use `alembic upgrade head` instead and set INIT_DB_TABLES=false.
    """
    import os
    if os.environ.get("INIT_DB_TABLES", "true").lower() in ("false", "0", "no"):
        logger.info("Skipping create_all() — INIT_DB_TABLES=false (use Alembic migrations)")
        return
    from db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables initialized (set INIT_DB_TABLES=false to use Alembic only)")

    # Lightweight in-place schema upgrades for columns added after first deploy.
    # `create_all` only creates *missing tables*, never alters existing tables,
    # so without Alembic running on startup we have to apply additive column
    # changes ourselves. PostgreSQL's `ADD COLUMN IF NOT EXISTS` makes this
    # idempotent and safe to run on every boot.
    _apply_inline_schema_upgrades(engine)


def _apply_inline_schema_upgrades(engine) -> None:
    """Idempotent ALTER TABLE statements for columns added in later releases.

    Each statement is wrapped in its own transaction so a failure on one
    upgrade does not abort the rest.
    """
    statements = [
        # Migration 003: link jobs/contracts to the email account that
        # created them so users can see all their deployments across the
        # multiple parties they create over different sessions.
        "ALTER TABLE job_history ADD COLUMN IF NOT EXISTS user_email TEXT",
        "CREATE INDEX IF NOT EXISTS idx_job_history_user_email ON job_history (user_email)",
        "ALTER TABLE deployed_contracts ADD COLUMN IF NOT EXISTS user_email TEXT",
        "CREATE INDEX IF NOT EXISTS idx_deployed_contracts_user_email ON deployed_contracts (user_email)",
    ]
    from sqlalchemy import text
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as e:
            logger.warning("Inline schema upgrade skipped", stmt=stmt, error=str(e))
