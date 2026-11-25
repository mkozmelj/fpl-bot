"""Watch lists: the Footballers each Member is thinking of buying (ticket 29).

Rows hold FPL element ids, which FPL renumbers every season, so every read and write is scoped to
the season of ``now``: last season's rows are simply not seen. Rows go with the Member on
``/leave`` through the ``ON DELETE CASCADE`` foreign key to ``members.id``.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.store.schema import Member, WatchedFootballer
from fplbot.store.seasons import season_of

WATCH_LIST_LIMIT = 20


class Added(Enum):
    ADDED = "added"
    ALREADY_THERE = "already_there"
    FULL = "full"


class WatchListStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def footballer_ids(self, chat_id: int, now: datetime) -> list[int]:
        """The Member's Watch list this season, oldest first."""
        async with self._sessions() as session:
            ids = await session.scalars(
                select(WatchedFootballer.footballer_id)
                .join(Member, Member.id == WatchedFootballer.member_id)
                .where(Member.chat_id == chat_id, WatchedFootballer.season == season_of(now))
                .order_by(WatchedFootballer.id)
            )
            return list(ids)

    async def add(self, chat_id: int, footballer_id: int, now: datetime) -> Added:
        season = season_of(now)
        async with self._sessions.begin() as session:
            # Locking the Member row serialises adds, so the limit holds.
            member_id = await session.scalar(
                select(Member.id).where(Member.chat_id == chat_id).with_for_update()
            )
            if member_id is None:  # left meanwhile: nothing to add to
                return Added.FULL
            mine = (WatchedFootballer.member_id == member_id, WatchedFootballer.season == season)
            existing = await session.scalar(
                select(WatchedFootballer.id).where(
                    *mine, WatchedFootballer.footballer_id == footballer_id
                )
            )
            if existing is not None:
                return Added.ALREADY_THERE
            count = await session.scalar(
                select(func.count()).select_from(WatchedFootballer).where(*mine)
            )
            if (count or 0) >= WATCH_LIST_LIMIT:
                return Added.FULL
            session.add(
                WatchedFootballer(
                    season=season, member_id=member_id, footballer_id=footballer_id, added_at=now
                )
            )
            return Added.ADDED

    async def remove(self, chat_id: int, footballer_id: int, now: datetime) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(WatchedFootballer).where(
                    WatchedFootballer.member_id
                    == select(Member.id).where(Member.chat_id == chat_id).scalar_subquery(),
                    WatchedFootballer.season == season_of(now),
                    WatchedFootballer.footballer_id == footballer_id,
                )
            )
