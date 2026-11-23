"""Reference data (clubs, Footballers, Gameweeks, fixtures) and each Member's history and picks.

Additive only (ADR 0003): new tables. Member tables reference ``members.id`` with ON DELETE
CASCADE so ``/leave`` hard-deletes them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _member_key() -> list[sa.Column[int] | sa.Column[str]]:
    return [
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("gameweek", sa.Integer(), primary_key=True, autoincrement=False),
    ]


def _reference_key() -> list[sa.Column[int] | sa.Column[str]]:
    return [
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
    ]


def upgrade() -> None:
    op.create_table(
        "clubs",
        *_reference_key(),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("short_name", sa.String(8), nullable=False),
    )
    op.create_table(
        "footballers",
        *_reference_key(),
        sa.Column("web_name", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("second_name", sa.String(100), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(3), nullable=False),
        sa.Column("now_cost", sa.Integer(), nullable=False),
    )
    op.create_table(
        "gameweeks",
        *_reference_key(),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished", sa.Boolean(), nullable=False),
        sa.Column("data_checked", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "fixtures",
        *_reference_key(),
        sa.Column("gameweek", sa.Integer(), nullable=True),
        sa.Column("kickoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("home_club_id", sa.Integer(), nullable=False),
        sa.Column("away_club_id", sa.Integer(), nullable=False),
        sa.Column("home_difficulty", sa.Integer(), nullable=True),
        sa.Column("away_difficulty", sa.Integer(), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("finished", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "member_gameweeks",
        *_member_key(),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("total_points", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("overall_rank", sa.Integer(), nullable=True),
        sa.Column("bank", sa.Integer(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("transfers", sa.Integer(), nullable=False),
        sa.Column("transfers_cost", sa.Integer(), nullable=False),
        sa.Column("points_on_bench", sa.Integer(), nullable=False),
        sa.Column("chip", sa.String(16), nullable=True),
    )
    op.create_table(
        "member_picks",
        *_member_key(),
        sa.Column("slot", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("footballer_id", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("is_captain", sa.Boolean(), nullable=False),
        sa.Column("is_vice_captain", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "member_picks",
        "member_gameweeks",
        "fixtures",
        "gameweeks",
        "footballers",
        "clubs",
    ):
        op.drop_table(table)
