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
    """Create all tables if they don't exist. Safe to call multiple times."""
    from db.models import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables initialized")
