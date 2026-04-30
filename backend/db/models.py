"""SQLAlchemy ORM models for Ginie application state.

Tables:
  - registered_parties: persistent party identities
  - user_sessions: JWT sessions tied to parties
  - job_history: contract generation job records (replaces Redis-only storage)
  - deployed_contracts: contracts deployed to Canton ledger
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Text, DateTime, ForeignKey, Index, JSON,
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
    # Direct ownership link for deploy-allocated parties. Populated when a
    # pipeline deploy allocates counterparties on behalf of an authenticated
    # user; remains NULL for parties registered via the standalone
    # /auth/register path (those still link via EmailAccount.party_id).
    user_email = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    sessions = relationship("UserSession", back_populates="party", cascade="all, delete-orphan")
    jobs = relationship("JobHistory", back_populates="party")


class EmailAccount(Base):
    """Email/password account that wraps a party identity.

    The email is the login credential. A party identity (Ed25519) is created
    after signup and linked here via party_id. Contracts are still owned by
    the party — the email is just a more familiar login layer.
    """

    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    display_name = Column(Text, nullable=True)
    party_id = Column(Text, ForeignKey("registered_parties.party_id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True), nullable=True)


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
    user_email = Column(Text, nullable=True, index=True)
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
        Index("idx_job_history_user_email", "user_email"),
    )


class DeployedContract(Base):
    __tablename__ = "deployed_contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Text, nullable=False)
    package_id = Column(Text, nullable=False, default="")
    template_id = Column(Text, nullable=False, default="")
    job_id = Column(Text, ForeignKey("job_history.job_id"), nullable=True)
    party_id = Column(Text, nullable=True)
    user_email = Column(Text, nullable=True, index=True)
    dar_path = Column(Text, nullable=True)
    canton_env = Column(Text, nullable=False, default="sandbox")
    explorer_link = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    job = relationship("JobHistory", back_populates="contracts")

    __table_args__ = (
        Index("idx_deployed_contracts_job", "job_id"),
        Index("idx_deployed_contracts_party", "party_id"),
        Index("idx_deployed_contracts_user_email", "user_email"),
    )


class JobEvent(Base):
    """Append-only event log for a generation/deployment job.

    Each row is one entry in the live log feed shown on the /sandbox page
    (and replayed on reload). Events are emitted from pipeline nodes with a
    structured `event_type` (e.g. ``stage_started:compile``) plus a
    human-readable ``message`` and optional JSON payload.
    """

    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Text, ForeignKey("job_history.job_id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, nullable=False, default=0)
    # Free-form taxonomy. Common prefixes: "stage_started:<stage>",
    # "stage_completed:<stage>", "stage_failed:<stage>", "log".
    event_type = Column(Text, nullable=False, default="log")
    # "info" | "warn" | "error" | "success" | "debug"
    level = Column(Text, nullable=False, default="info")
    message = Column(Text, nullable=False, default="")
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_job_events_job_seq", "job_id", "seq"),
        Index("idx_job_events_job", "job_id"),
    )


class InviteCode(Base):
    """Invite codes for invite-only signup.
    
    Each code can be used once. After a successful signup, the code is marked
    as used and linked to the email account that claimed it.
    """

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, nullable=False, unique=True, index=True)
    used = Column(Integer, nullable=False, default=0)
    used_by_email = Column(Text, nullable=True, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_invite_codes_used", "used"),
    )
