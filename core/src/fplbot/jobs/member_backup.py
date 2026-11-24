"""The nightly Member backup (ticket 23, ticket 39).

Exports the Member and config tables (``store/backup.py``), encrypts the export with ``age`` to
``BACKUP_AGE_PUBLIC_KEY`` and sends it as a document to the owner's chat, keeping the last 7.

Telegram lets a bot delete a message only while it is under 48 hours old, so a week-old backup
cannot be deleted. Instead the chat holds at most 7 backup messages: until there are 7, each
backup is a new message; after that, each backup overwrites the message holding the oldest one
(``editMessageMedia``), so the older backup is gone. If the owner deleted that message by hand,
a new message is sent instead.

Scheduling (ticket 31): ``app.py`` registers ``daily(MEMBER_BACKUP_JOB, ..., MEMBER_BACKUP_AT,
MEMBER_BACKUP_ZONE)`` with the scheduler: once a day at 04:00 UK time, priority
``Priority.ROUTINE``. It makes no FPL requests.

One backup per UK day: a sent backup gets a ``member-backup`` completion row for its UK date,
so a re-run that day (the scheduler re-fires a run after a restart inside its grace window)
sends nothing.
"""

import logging
from datetime import time
from typing import Protocol
from zoneinfo import ZoneInfo

import pyrage
from sqlalchemy.ext.asyncio import AsyncEngine

from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.sources.fpl import FplSource
from fplbot.store.backup import BackupMessages, export_member_tables
from fplbot.store.completions import CompletionStore, night_period
from fplbot.store.owner_notices import OwnerNotices
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)

MEMBER_BACKUP_JOB = "member-backup"
# After the 00:10 price-change archive, when nothing else runs.
MEMBER_BACKUP_AT = time(4, 0)
MEMBER_BACKUP_ZONE = ZoneInfo("Europe/London")
# Backups kept in the owner's chat.
BACKUPS_KEPT = 7
NO_KEY_NOTICE = "backup-no-key"


class OwnerChat(Protocol):
    """The owner's Telegram chat, as the backup needs it."""

    async def send_text(self, text: str) -> None: ...

    async def send_document(self, filename: str, content: bytes, caption: str) -> int:
        """Send a file; returns the new message's id."""
        ...

    async def replace_document(
        self, message_id: int, filename: str, content: bytes, caption: str
    ) -> bool:
        """Put a new file into one of the bot's document messages; ``False`` if that message
        is gone (the owner deleted it)."""
        ...


class MemberBackup:
    def __init__(
        self, engine: AsyncEngine, public_key: str | None, owner: OwnerChat, clock: Clock
    ) -> None:
        self._engine = engine
        self._notices = OwnerNotices(engine)
        self._messages = BackupMessages(engine)
        self._completions = CompletionStore(engine)
        self._recipient = pyrage.x25519.Recipient.from_str(public_key) if public_key else None
        self._owner = owner
        self._clock = clock

    async def run(self, fpl: FplSource) -> None:
        """The job: one encrypted backup to the owner's chat, or (once) a note that no key is
        configured."""
        del fpl  # the backup reads only the database
        now = self._clock.now()
        if self._recipient is None:
            if await self._notices.claim(NO_KEY_NOTICE, now):
                try:
                    await self._owner.send_text(texts.MEMBER_BACKUP_NO_KEY)
                except Exception:
                    await self._notices.clear(NO_KEY_NOTICE)
                    raise
            log.info("member backup skipped: no public key")
            return
        await self._notices.clear(NO_KEY_NOTICE)
        season, period = season_of(now), night_period(now.astimezone(MEMBER_BACKUP_ZONE).date())
        if await self._completions.done(MEMBER_BACKUP_JOB, season, period):
            log.info("member backup already sent today")
            return

        export = await export_member_tables(self._engine, now)
        filename = f"fplbot-members-{now:%Y-%m-%d}.sql.age"
        content = pyrage.encrypt(export.sql.encode(), [self._recipient])
        caption = texts.member_backup_caption(now, export.members)

        oldest = await self._messages.oldest_if_full(BACKUPS_KEPT)
        if oldest is not None:
            if await self._owner.replace_document(oldest, filename, content, caption):
                await self._messages.rewritten(oldest, now)
                await self._completions.record(MEMBER_BACKUP_JOB, season, period, now)
                log.info("member backup sent over the oldest: %d Members", export.members)
                return
            await self._messages.forget(oldest)
        message_id = await self._owner.send_document(filename, content, caption)
        await self._messages.record(message_id, now)
        await self._completions.record(MEMBER_BACKUP_JOB, season, period, now)
        log.info("member backup sent: %d Members", export.members)
