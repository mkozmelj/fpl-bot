"""Price history (ticket 37): evening price snapshots, the nightly Price-change archive (with a
row per archived night), the projection codes at Price-alert time, and the news/status log.

Additive only (ADR 0003): new tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_snapshots",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("footballer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("price", sa.SmallInteger(), nullable=False),
        sa.Column("percent", sa.SmallInteger()),
        sa.Column("hourly_rate", sa.Integer()),
        sa.Column("likelihood_tonight", sa.SmallInteger()),
        sa.Column("likelihood_tomorrow", sa.SmallInteger()),
        sa.Column("likelihood_after", sa.SmallInteger()),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("calibrating", sa.Boolean()),
    )
    op.create_table(
        "price_changes",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("footballer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("night", sa.Date(), nullable=False),
        sa.Column("gameweek", sa.Integer()),
        sa.Column("club_id", sa.Integer()),
        sa.Column("cost_before", sa.SmallInteger(), nullable=False),
        sa.Column("cost_after", sa.SmallInteger(), nullable=False),
    )
    op.create_index("ix_price_changes_night", "price_changes", ["night"])
    op.create_table(
        "price_archive_nights",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("night", sa.Date(), primary_key=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "price_predictions",
        sa.Column("season", sa.String(7), primary_key=True),
        sa.Column("night", sa.Date(), primary_key=True),
        sa.Column("footballer_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("made_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tonight", sa.SmallInteger()),
        sa.Column("tomorrow", sa.SmallInteger()),
    )
    op.create_table(
        "footballer_news",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("footballer_id", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("news", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_footballer_news_latest", "footballer_news", ["season", "footballer_id", "observed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_footballer_news_latest", table_name="footballer_news")
    op.drop_table("footballer_news")
    op.drop_table("price_predictions")
    op.drop_table("price_archive_nights")
    op.drop_index("ix_price_changes_night", table_name="price_changes")
    op.drop_table("price_changes")
    op.drop_table("price_snapshots")
