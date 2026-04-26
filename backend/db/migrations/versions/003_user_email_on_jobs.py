"""Link jobs and deployed contracts to the email account that created them.

This decouples the user identity (stable email) from the per-session party
identity, so users can see all contracts they ever deployed across the
different parties they create on each login.

Revision ID: 003
Revises: 002
Create Date: 2026-04-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_history", sa.Column("user_email", sa.Text(), nullable=True))
    op.create_index("idx_job_history_user_email", "job_history", ["user_email"])

    op.add_column("deployed_contracts", sa.Column("user_email", sa.Text(), nullable=True))
    op.create_index("idx_deployed_contracts_user_email", "deployed_contracts", ["user_email"])


def downgrade() -> None:
    op.drop_index("idx_deployed_contracts_user_email", table_name="deployed_contracts")
    op.drop_column("deployed_contracts", "user_email")

    op.drop_index("idx_job_history_user_email", table_name="job_history")
    op.drop_column("job_history", "user_email")
