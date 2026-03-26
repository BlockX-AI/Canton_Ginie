"""Initial schema for Ginie application state.

Revision ID: 001
Revises: None
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registered_parties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("party_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("public_key_fp", sa.Text(), nullable=True),
        sa.Column("canton_env", sa.Text(), nullable=False, server_default="sandbox"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("party_id"),
    )
    op.create_index("ix_registered_parties_party_id", "registered_parties", ["party_id"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("party_id", sa.Text(), nullable=False),
        sa.Column("jwt_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.ForeignKeyConstraint(["party_id"], ["registered_parties.party_id"]),
    )
    op.create_index("ix_user_sessions_session_id", "user_sessions", ["session_id"])

    op.create_table(
        "job_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("party_id", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.Text(), nullable=False, server_default="idle"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canton_env", sa.Text(), nullable=False, server_default="sandbox"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
        sa.ForeignKeyConstraint(["party_id"], ["registered_parties.party_id"]),
    )
    op.create_index("ix_job_history_job_id", "job_history", ["job_id"])
    op.create_index("idx_job_history_status", "job_history", ["status"])
    op.create_index("idx_job_history_party", "job_history", ["party_id"])

    op.create_table(
        "deployed_contracts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contract_id", sa.Text(), nullable=False),
        sa.Column("package_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("job_id", sa.Text(), nullable=True),
        sa.Column("party_id", sa.Text(), nullable=True),
        sa.Column("dar_path", sa.Text(), nullable=True),
        sa.Column("canton_env", sa.Text(), nullable=False, server_default="sandbox"),
        sa.Column("explorer_link", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["job_history.job_id"]),
    )
    op.create_index("idx_deployed_contracts_job", "deployed_contracts", ["job_id"])
    op.create_index("idx_deployed_contracts_party", "deployed_contracts", ["party_id"])


def downgrade() -> None:
    op.drop_table("deployed_contracts")
    op.drop_table("job_history")
    op.drop_table("user_sessions")
    op.drop_table("registered_parties")
