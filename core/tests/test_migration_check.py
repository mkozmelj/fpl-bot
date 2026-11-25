"""The CI check that keeps migrations expand-only unless labelled as a contract step (ADR 0003)."""

from pathlib import Path

import pytest

from fplbot.store import migration_check

DROP_COLUMN = '''
"""Drop members.joined_at."""

import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098"
{label}

def upgrade() -> None:
    op.drop_column("members", "joined_at")


def downgrade() -> None:
    op.add_column("members", sa.Column("joined_at", sa.DateTime(timezone=True)))
'''


def write_migration(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source)
    return path


def test_rejects_a_drop_column_migration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_migration(tmp_path, "0099_drop_joined_at.py", DROP_COLUMN.format(label=""))

    assert migration_check.main([str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "0099_drop_joined_at.py" in output
    assert "drop_column" in output


def test_accepts_a_drop_column_migration_labelled_as_a_contract_step(tmp_path: Path) -> None:
    write_migration(
        tmp_path, "0099_drop_joined_at.py", DROP_COLUMN.format(label="contract_step = True")
    )

    assert migration_check.main([str(tmp_path)]) == 0


def migration_with_upgrade(body: str) -> str:
    return f"""
import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098"


def upgrade() -> None:
    {body}


def downgrade() -> None:
    op.drop_table("watch_list")
"""


@pytest.mark.parametrize(
    "body",
    [
        'op.rename_table("members", "managers")',
        'op.alter_column("members", "chat_id", new_column_name="telegram_chat_id")',
        'op.drop_table("invites")',
        'op.execute("ALTER TABLE members DROP COLUMN joined_at")',
        'op.execute(sa.text("alter table members rename column chat_id to telegram_chat_id"))',
        'with op.batch_alter_table("members") as batch:\n        batch.drop_column("joined_at")',
    ],
)
def test_rejects_drops_and_renames_however_they_are_written(tmp_path: Path, body: str) -> None:
    write_migration(tmp_path, "0099_change.py", migration_with_upgrade(body))

    assert migration_check.main([str(tmp_path)]) == 1


@pytest.mark.parametrize(
    "body",
    [
        'op.add_column("members", sa.Column("timezone", sa.String(64), nullable=True))',
        'op.alter_column("members", "chat_id", nullable=True)',
        "op.execute(\"UPDATE members SET season = '2026-27'\")",
    ],
)
def test_accepts_expand_only_migrations_even_when_downgrade_drops(
    tmp_path: Path, body: str
) -> None:
    write_migration(tmp_path, "0099_change.py", migration_with_upgrade(body))

    assert migration_check.main([str(tmp_path)]) == 0


def test_the_repository_migrations_pass() -> None:
    assert migration_check.main([]) == 0
