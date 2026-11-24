"""Ticket 42: a rollback runs the previous image against the newer schema (ADR 0003).

Migrations are expand-only, so an image must start against a database that a newer image has
already migrated further, and its pre-deploy migration must leave that database alone. A database
*behind* the image still stops startup, so the smoke check sees no ``ready`` line.
"""

import logging
from collections.abc import Iterator

import psycopg
import pytest

from fplbot.__main__ import main
from tests.harness import DEPLOY_SHA, BotHarness

NEWER_REVISION = "0999_from_a_newer_image"


def _set_revision(database_url: str, revision: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("UPDATE alembic_version SET version_num = %s", (revision,))


@pytest.fixture
def schema_revision(empty_database: str) -> Iterator[str]:
    """Lets a test move the database's recorded revision; restores this code's head after."""
    with psycopg.connect(empty_database, autocommit=True) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    head = str(row[0])
    yield head
    _set_revision(empty_database, head)


async def test_after_a_rollback_the_previous_image_starts_on_the_newer_schema(
    bot: BotHarness, empty_database: str, schema_revision: str
) -> None:
    _set_revision(empty_database, NEWER_REVISION)

    await bot.start_up()

    assert [line for line in bot.logs if "ready sha=" in line] == [
        f"fplbot.app ready sha={DEPLOY_SHA}"
    ]


async def test_a_database_behind_this_image_stops_startup_before_ready(
    bot: BotHarness, empty_database: str, schema_revision: str
) -> None:
    _set_revision(empty_database, "0007")  # a known, older revision: pre-deploy didn't run

    with pytest.raises(RuntimeError):
        await bot.start_up()

    assert "fplbot.app startup aborted: the database is not at the latest migration" in bot.logs
    assert not [line for line in bot.logs if "ready sha=" in line]


def test_the_pre_deploy_migration_leaves_a_newer_schema_alone(
    empty_database: str,
    schema_revision: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_revision(empty_database, NEWER_REVISION)
    monkeypatch.setenv("DATABASE_URL", empty_database)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")

    with caplog.at_level(logging.INFO, logger="fplbot"):
        exit_code = main(["migrate"])  # Railway's pre-deploy command: `fplbot migrate`

    assert exit_code == 0
    assert (
        "the database is ahead of this image (a rollback?): nothing to migrate" in caplog.messages
    )
    with psycopg.connect(empty_database) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row == (NEWER_REVISION,)
