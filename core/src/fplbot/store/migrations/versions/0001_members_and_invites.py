"""Members and invites.

Revision ID: 0001
Revises:
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("invites")
    op.drop_table("members")
