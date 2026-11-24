"""Ticket 39: a nightly age-encrypted export of the Member tables, sent to the owner's chat."""

import os
import re
import secrets
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from typing import Any

import psycopg
import pyrage
import pytest
from psycopg import sql
from sqlalchemy import make_url

from fplbot.jobs.member_backup import MEMBER_BACKUP_JOB
from fplbot.store import migrate
from tests.harness import BACKUP_IDENTITY, BotHarness, SentDocument

MEMBER_TABLES = ("members", "invites", "watch_list")


async def nightly_backup(bot: BotHarness) -> bool:
    return await bot.run_job(MEMBER_BACKUP_JOB, bot.app.member_backup.run)


def decrypted(document: SentDocument) -> str:
    return pyrage.decrypt(document.content, [BACKUP_IDENTITY]).decode()


def rows_of(database_url: str, table: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(database_url) as connection:
        query = sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))
        return connection.execute(query).fetchall()


@pytest.fixture
def scratch_database(database_url: str) -> Iterator[str]:
    """An empty database migrated to head, like the restore drill's: dropped afterwards."""
    admin_url = os.environ["TEST_DATABASE_URL"]
    name = f"fplbot_restore_{os.getpid()}_{secrets.token_hex(4)}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    try:
        migrate.upgrade(url)
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


async def test_the_owner_receives_an_encrypted_backup_that_restores_the_member_tables(
    bot: BotHarness, scratch_database: str
) -> None:
    alice = await bot.active_member(2001, 1001)
    await bot.active_member(2002, 1002, timezone="Europe/Paris")
    await alice.send("/watch add fakesson")
    await bot.owner.send("/invite")  # an unused invite
    assert alice.last_reply.startswith("Added Fakesson")

    assert await nightly_backup(bot)

    [backup] = bot.owner.documents
    assert backup.filename.endswith(".sql.age")
    with psycopg.connect(scratch_database, autocommit=True) as restored:
        restored.execute(decrypted(backup).encode())
        next_member = restored.execute(
            "SELECT nextval(pg_get_serial_sequence('members', 'id'))"
        ).fetchone()
    for table in MEMBER_TABLES:
        assert rows_of(scratch_database, table) == rows_of(bot.config.database_url, table)
    assert len(rows_of(scratch_database, "members")) == 2
    assert len(rows_of(scratch_database, "watch_list")) == 1
    assert next_member == (3,)  # a restored bot numbers the next Member after the restored ones


async def test_the_backup_holds_only_the_member_and_config_tables(bot: BotHarness) -> None:
    await bot.active_member(2001, 1001)
    await nightly_backup(bot)
    await bot.advance(timedelta(days=1))
    await nightly_backup(bot)  # the first backup's own bookkeeping exists by now

    statements = [
        line
        for line in decrypted(bot.owner.documents[-1]).splitlines()
        if line and not line.startswith("--")
    ]
    inserted_into = {m.group(1) for s in statements if (m := re.match(r'INSERT INTO "(\w+)"', s))}
    assert inserted_into == {"members", "invites"}
    assert all(
        s.startswith(("BEGIN;", "COMMIT;", "INSERT INTO", "SELECT pg_catalog.setval("))
        for s in statements
    )


async def test_without_a_public_key_the_backup_is_skipped_and_the_owner_told_once(
    bot: BotHarness,
) -> None:
    without_key = replace(bot.config, backup_public_key=None)
    await bot.restart(without_key)

    assert await nightly_backup(bot)
    await bot.advance(timedelta(days=1))
    assert await nightly_backup(bot)
    await bot.restart(without_key)  # a deploy does not repeat the notice
    await bot.advance(timedelta(days=1))
    assert await nightly_backup(bot)

    assert bot.owner.documents == []
    assert bot.owner.replies == [
        "Member backup skipped: BACKUP_AGE_PUBLIC_KEY is not set. Set it to an age public key "
        "to get a nightly encrypted backup here (docs/runbook-secrets.md)."
    ]


def caption_on(day: int) -> str:
    return (
        f"Member backup, {day} Nov 2026 18:00 UTC: 0 Members. Encrypted with age; "
        "the restore drill is in docs/runbook-secrets.md."
    )


def backup_dates(bot: BotHarness) -> list[str]:
    """The ``taken`` date in each backup the owner's chat holds, oldest first."""
    return sorted(decrypted(d).split()[5] for d in bot.owner.documents)


async def run_nights(bot: BotHarness, nights: int) -> None:
    for _ in range(nights):
        assert await nightly_backup(bot)
        await bot.advance(timedelta(days=1))


async def test_only_the_last_7_backups_stay_in_the_owner_chat_across_restarts(
    bot: BotHarness,
) -> None:
    await run_nights(bot, 5)
    await bot.restart()
    await run_nights(bot, 4)  # nights 6 to 9: 23 to 27 Nov

    # Telegram lets a bot delete only messages under 48 hours old, so the oldest backup's
    # message is overwritten with the new backup instead.
    assert len(bot.owner.documents) == 7
    assert sorted(d.caption or "" for d in bot.owner.documents) == [
        caption_on(day) for day in range(21, 28)
    ]
    assert backup_dates(bot) == [f"2026-11-{day}" for day in range(21, 28)]


async def test_a_backup_the_owner_deleted_by_hand_is_replaced_by_a_new_message(
    bot: BotHarness,
) -> None:
    await run_nights(bot, 7)
    oldest = bot.owner.documents[0]
    bot.telegram.delete_by_hand(oldest.chat_id, oldest.message_id)

    await run_nights(bot, 2)  # night 8 cannot overwrite the deleted one; night 9 replaces night 2

    assert len(bot.owner.documents) == 7
    assert backup_dates(bot) == [f"2026-11-{day}" for day in range(21, 28)]
    assert bot.owner.replies == []


async def test_the_backup_runs_by_itself_every_night_at_04_00_uk_time(bot: BotHarness) -> None:
    await bot.start_scheduling()  # Thu 19 Nov 18:00 UTC

    await bot.advance(timedelta(days=1, hours=10, minutes=30))  # Sat 21 Nov 04:30 UTC

    assert sorted(d.caption or "" for d in bot.owner.documents) == [
        caption_on(day).replace("18:00", "04:00") for day in (20, 21)
    ]
