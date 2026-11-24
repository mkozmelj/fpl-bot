"""Job completion rows: one per idempotent job (picks, elite, gw_final, price_archive) and period.

Additive only (ADR 0003): a new table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_completions",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("job", sa.String(32), primary_key=True),
        sa.Column("period", sa.String(16), primary_key=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("job_completions")
