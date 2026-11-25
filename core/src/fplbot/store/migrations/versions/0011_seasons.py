"""Seasons: the current season, and a new one waiting for the owner's /rollover (ticket 40).

Additive only (ADR 0003): a new table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("seasons")
