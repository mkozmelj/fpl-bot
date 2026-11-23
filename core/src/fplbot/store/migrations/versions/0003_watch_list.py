"""Watch list: the Footballers each Member is thinking of buying.

Additive only (ADR 0003): a new table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watch_list",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("footballer_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("member_id", "season", "footballer_id"),
    )
    op.create_index("ix_watch_list_member_id", "watch_list", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_watch_list_member_id", table_name="watch_list")
    op.drop_table("watch_list")
