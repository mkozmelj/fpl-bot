"""One-time owner notices: DMs the owner gets once, not once per process (ticket 39).

A notice is a short fixed key such as ``"backup-no-key"``. Clearing it (when the condition is
gone) lets it be sent again if the condition comes back.
"""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from fplbot.store.schema import OwnerNotice
from fplbot.store.seasons import season_of


class OwnerNotices:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def claim(self, notice: str, now: datetime) -> bool:
        """Record ``notice`` as sent; ``True`` if it had not been sent before (send it now)."""
        async with self._engine.begin() as connection:
            inserted = await connection.scalar(
                insert(OwnerNotice)
                .values(season=season_of(now), notice=notice, sent_at=now)
                .on_conflict_do_nothing(index_elements=[OwnerNotice.notice])
                .returning(OwnerNotice.id)
            )
        return inserted is not None

    async def clear(self, notice: str) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(delete(OwnerNotice).where(OwnerNotice.notice == notice))
