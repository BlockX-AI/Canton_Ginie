"""SQLAlchemy ORM models for Ginie application state.

Tables:
  - registered_parties: persistent party identities
  - user_sessions: JWT sessions tied to parties
  - job_history: contract generation job records (replaces Redis-only storage)
  - deployed_contracts: contracts deployed to Canton ledger
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Text, Boolean, DateTime, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class RegisteredParty(Base):
    __tablename__ = "registered_parties"

    id = Column(Integer, primary_key=True, autoincrement=True)
    party_id = Column(Text, nullable=False, unique=True, index=True)
    display_name = Column(Text, nullable=False)
    public_key_fp = Column(Text, nullable=True)
    canton_env = Column(Text, nullable=False, default="sandbox")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    sessions = relationship("UserSession", back_populates="party", cascade="all, delete-orphan")
    jobs = relationship("JobHistory", back_populates="party")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False, unique=True, index=True)
    party_id = Column(Text, ForeignKey("registered_parties.party_id"), nullable=False)
    jwt_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    party = relationship("RegisteredParty", back_populates="sessions")


class JobHistory(Base):
    __tablename__ = "job_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Text, nullable=False, unique=True, index=True)
    party_id = Column(Text, ForeignKey("registered_parties.party_id"), nullable=True)
    prompt = Column(Text, nullable=False, default="")
    status = Column(Text, nullable=False, default="pending")
    current_step = Column(Text, nullable=False, default="idle")
    progress = Column(Integer, nullable=False, default=0)
    canton_env = Column(Text, nullable=False, default="sandbox")
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    party = relationship("RegisteredParty", back_populates="jobs")
    contracts = relationship("DeployedContract", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_job_history_status", "status"),
        Index("idx_job_history_party", "party_id"),
    )


class DeployedContract(Base):
    __tablename__ = "deployed_contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Text, nullable=False)
    package_id = Column(Text, nullable=False, default="")
    template_id = Column(Text, nullable=False, default="")
    job_id = Column(Text, ForeignKey("job_history.job_id"), nullable=True)
    party_id = Column(Text, nullable=True)
    dar_path = Column(Text, nullable=True)
    canton_env = Column(Text, nullable=False, default="sandbox")
    explorer_link = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    job = relationship("JobHistory", back_populates="contracts")

    __table_args__ = (
        Index("idx_deployed_contracts_job", "job_id"),
        Index("idx_deployed_contracts_party", "party_id"),
    )
