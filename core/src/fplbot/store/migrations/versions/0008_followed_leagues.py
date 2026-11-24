"""Followed leagues: the Mini-league tables kept for Members, their links and H2H opponents.

Additive only (ADR 0003): new tables. Member links reference ``members.id`` with ON DELETE
CASCADE so ``/leave`` hard-deletes them.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEAGUE_KEY = ["season", "kind", "league_id"]
_LEAGUE_REF = [f"followed_leagues.{column}" for column in _LEAGUE_KEY]


def _league_key() -> list[sa.Column[int] | sa.Column[str]]:
    return [
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("kind", sa.String(8), primary_key=True),
        sa.Column("league_id", sa.BigInteger(), primary_key=True, autoincrement=False),
    ]


def _member_id() -> sa.Column[int]:
    return sa.Column(
        "member_id",
        sa.Integer(),
        sa.ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    )


def upgrade() -> None:
    op.create_table(
        "followed_leagues",
        *_league_key(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("gameweek", sa.Integer(), nullable=True),
        sa.Column("gameweek_finished", sa.Boolean(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "league_standings",
        *_league_key(),
        sa.Column("position", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("entry_id", sa.BigInteger(), nullable=False),
        sa.Column("team_name", sa.String(100), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("last_rank", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(_LEAGUE_KEY, _LEAGUE_REF, ondelete="CASCADE"),
    )
    op.create_table(
        "member_leagues",
        _member_id(),
        *_league_key(),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(_LEAGUE_KEY, _LEAGUE_REF, ondelete="CASCADE"),
    )
    op.create_table(
        "h2h_opponents",
        _member_id(),
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("league_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("gameweek", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("opponent_entry_id", sa.BigInteger(), nullable=True),
        sa.Column("opponent_team_name", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("h2h_opponents")
    op.drop_table("member_leagues")
    op.drop_table("league_standings")
    op.drop_table("followed_leagues")
