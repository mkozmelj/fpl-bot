"""Member setup and settings: linked team, Goal, timezone, Price alert time.

Additive only (ADR 0003): every new column is nullable or has a server default, so the previous
image keeps working against the migrated schema.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("status", sa.String(16), nullable=False, server_default="joining"),
    )
    op.add_column("members", sa.Column("team_id", sa.BigInteger(), nullable=True))
    op.add_column("members", sa.Column("team_name", sa.String(100), nullable=True))
    op.add_column("members", sa.Column("goal", sa.String(16), nullable=True))
    op.add_column("members", sa.Column("league_id", sa.BigInteger(), nullable=True))
    op.add_column("members", sa.Column("league_kind", sa.String(8), nullable=True))
    op.add_column("members", sa.Column("league_name", sa.String(100), nullable=True))
    op.add_column("members", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column(
        "members",
        sa.Column("alert_time", sa.Time(), nullable=False, server_default=sa.text("'20:00'")),
    )
    op.create_unique_constraint("members_team_id_key", "members", ["team_id"])


def downgrade() -> None:
    op.drop_constraint("members_team_id_key", "members", type_="unique")
    for column in (
        "alert_time",
        "timezone",
        "league_name",
        "league_kind",
        "league_id",
        "goal",
        "team_name",
        "team_id",
        "status",
    ):
        op.drop_column("members", column)
