"""Rival picks (kept for the season) and per-Gameweek Footballer stats (kept across seasons).

Additive only (ADR 0003): new tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rival_picks",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("entry_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("gameweek", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("slot", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("footballer_id", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("is_captain", sa.Boolean(), nullable=False),
        sa.Column("is_vice_captain", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "footballer_gameweek_stats",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("gameweek", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("footballer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("total_points", sa.SmallInteger(), nullable=False),
        sa.Column("minutes", sa.SmallInteger(), nullable=False),
        sa.Column("starts", sa.SmallInteger(), nullable=True),
        sa.Column("goals_scored", sa.SmallInteger(), nullable=True),
        sa.Column("assists", sa.SmallInteger(), nullable=True),
        sa.Column("clean_sheets", sa.SmallInteger(), nullable=True),
        sa.Column("goals_conceded", sa.SmallInteger(), nullable=True),
        sa.Column("saves", sa.SmallInteger(), nullable=True),
        sa.Column("bonus", sa.SmallInteger(), nullable=True),
        sa.Column("bps", sa.SmallInteger(), nullable=True),
        sa.Column("expected_goals", sa.Float(), nullable=True),
        sa.Column("expected_assists", sa.Float(), nullable=True),
        sa.Column("expected_goals_conceded", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("footballer_gameweek_stats")
    op.drop_table("rival_picks")
