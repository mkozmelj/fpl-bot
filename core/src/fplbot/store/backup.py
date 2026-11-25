"""The Member backup's export (ticket 23, ticket 39): the small, irreplaceable tables as SQL.

Only the Member and config tables are exported: ``members`` (with each Member's Goal and
settings), ``invites`` and ``watch_list``. The large tables (price snapshots, Elite aggregates)
rely on Neon's restore window and the backfill job, so they are never in a backup. A new table
holding Member data or settings joins ``BACKUP_TABLES`` here (parents before children).

The export is plain ``INSERT`` statements in one transaction, for an empty database migrated to
the schema revision named in the header (the runbook's restore drill: ``psql -f``).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import sql
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from fplbot.store.schema import Base, MemberBackupMessage
from fplbot.store.seasons import season_of

# Restore order: tables referenced by foreign keys first.
BACKUP_TABLES = ("members", "invites", "watch_list")


@dataclass(frozen=True)
class MemberExport:
    sql: str
    members: int


async def export_member_tables(engine: AsyncEngine, taken_at: datetime) -> MemberExport:
    """One consistent snapshot of ``BACKUP_TABLES`` as a restorable SQL script."""
    lines: list[str] = []
    members = 0
    async with engine.connect() as connection:
        await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        lines += [
            f"-- fplbot Member backup taken {taken_at:%Y-%m-%d %H:%M} UTC.",
            f"-- Schema revision {revision}. Restore into an empty database migrated to that",
            "-- revision: psql -f <file> (docs/runbook-secrets.md, Restore drill).",
            "BEGIN;",
        ]
        for name in BACKUP_TABLES:
            table = Base.metadata.tables[name]
            rows = (await connection.execute(select(table).order_by(table.c.id))).all()
            columns = [column.name for column in table.columns]
            lines += [_insert(name, columns, tuple(row)) for row in rows]
            if rows:
                lines.append(_set_sequence(name, max(row.id for row in rows)))
            if name == "members":
                members = len(rows)
        lines.append("COMMIT;")
    return MemberExport(sql="\n".join(lines) + "\n", members=members)


def _insert(table: str, columns: list[str], row: tuple[Any, ...]) -> str:
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({});").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(map(sql.Literal, row)),
    )
    return statement.as_string(None)


def _set_sequence(table: str, last_id: int) -> str:
    """Restored rows keep their ids, so the next new row must be numbered after them."""
    statement = sql.SQL("SELECT pg_catalog.setval(pg_get_serial_sequence({}, 'id'), {});").format(
        sql.Literal(table), sql.Literal(last_id)
    )
    return statement.as_string(None)


class BackupMessages:
    """The backup documents in the owner's chat, by Telegram message id, with when each last
    received a backup."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, message_id: int, sent_at: datetime) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                insert(MemberBackupMessage).values(
                    season=season_of(sent_at), message_id=message_id, sent_at=sent_at
                )
            )

    async def oldest_if_full(self, kept: int) -> int | None:
        """The message holding the oldest backup once ``kept`` messages exist, else None."""
        async with self._engine.connect() as connection:
            ids = (
                await connection.scalars(
                    select(MemberBackupMessage.message_id).order_by(
                        MemberBackupMessage.sent_at, MemberBackupMessage.id
                    )
                )
            ).all()
        return ids[0] if len(ids) >= kept else None

    async def rewritten(self, message_id: int, sent_at: datetime) -> None:
        """``message_id`` now holds the backup taken at ``sent_at``."""
        async with self._engine.begin() as connection:
            await connection.execute(
                update(MemberBackupMessage)
                .where(MemberBackupMessage.message_id == message_id)
                .values(season=season_of(sent_at), sent_at=sent_at)
            )

    async def forget(self, message_id: int) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                delete(MemberBackupMessage).where(MemberBackupMessage.message_id == message_id)
            )
