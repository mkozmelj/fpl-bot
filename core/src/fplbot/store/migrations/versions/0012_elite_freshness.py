"""Elite sample freshness (ticket 35): partial samples and late cohort reads.

Additive only (ADR 0003): two columns with defaults, so rows from ticket 34 read as full,
on-time samples.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("partial", "read_late"):
        op.add_column(
            "elite_samples",
            sa.Column(column, sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    for column in ("read_late", "partial"):
        op.drop_column("elite_samples", column)
