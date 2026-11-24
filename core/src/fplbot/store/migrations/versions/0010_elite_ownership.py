"""Elite ownership aggregates (ticket 34), kept across seasons.

Additive only (ADR 0003): new tables.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-24
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SAMPLE_KEY = ["season", "gameweek", "cohort"]
_SAMPLE_REF = [f"elite_samples.{column}" for column in _SAMPLE_KEY]


def _key() -> list[sa.Column[Any]]:
    return [
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("gameweek", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("cohort", sa.String(8), primary_key=True),
    ]


def upgrade() -> None:
    op.create_table(
        "elite_samples",
        *_key(),
        sa.Column("cohort_size", sa.Integer(), nullable=False),
        sa.Column("target_size", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("margin_of_error", sa.Float(), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "elite_ownership",
        *_key(),
        sa.Column("footballer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("ownership", sa.Float(), nullable=False),
        sa.Column("xi_share", sa.Float(), nullable=False),
        sa.Column("captain_share", sa.Float(), nullable=False),
        sa.Column("eo", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(_SAMPLE_KEY, _SAMPLE_REF, ondelete="CASCADE"),
    )
    op.create_table(
        "elite_chips",
        *_key(),
        sa.Column("chip", sa.String(16), primary_key=True),
        sa.Column("share", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(_SAMPLE_KEY, _SAMPLE_REF, ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("elite_chips")
    op.drop_table("elite_ownership")
    op.drop_table("elite_samples")
