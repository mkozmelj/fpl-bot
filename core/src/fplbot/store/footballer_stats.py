"""Per-Gameweek Footballer stats (ticket 33), kept across seasons.

Written once per finished Gameweek from ``event/{gw}/live/`` (``jobs/footballer_stats.py``).
Footballer ids are FPL element ids, renumbered every season, so every read is per ``season``.
"""

from collections.abc import Iterable
from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.sources.fpl import FplLiveFootballer
from fplbot.store.schema import FootballerGameweekStats

# The Gap's Phase 1 weight: average points over this many finished Gameweeks.
RECENT_GAMEWEEKS = 4


class FootballerStatsStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def save(
        self, season: str, gameweek: int, footballers: Iterable[FplLiveFootballer]
    ) -> None:
        """Store (or overwrite) every Footballer's stats for ``gameweek``."""
        rows = [{"season": season, "gameweek": gameweek, **asdict(f)} for f in footballers]
        if not rows:
            return
        statement = insert(FootballerGameweekStats).values(rows)
        keys = ("season", "gameweek", "footballer_id")
        updated = {k: statement.excluded[k] for k in rows[0] if k not in keys}
        async with self._sessions.begin() as session:
            await session.execute(
                statement.on_conflict_do_update(index_elements=keys, set_=updated)
            )

    async def average_points(
        self, season: str, gameweeks: int = RECENT_GAMEWEEKS
    ) -> dict[int, float]:
        """Each Footballer's average points over the latest ``gameweeks`` Gameweeks with stored
        stats (fewer early in the season). A Footballer missing from one of them (e.g. not yet
        signed) counts 0 there. Empty when nothing is stored."""
        async with self._sessions() as session:
            recent = list(
                await session.scalars(
                    select(FootballerGameweekStats.gameweek)
                    .where(FootballerGameweekStats.season == season)
                    .distinct()
                    .order_by(FootballerGameweekStats.gameweek.desc())
                    .limit(gameweeks)
                )
            )
            if not recent:
                return {}
            rows = await session.execute(
                select(
                    FootballerGameweekStats.footballer_id,
                    func.sum(FootballerGameweekStats.total_points),
                )
                .where(
                    FootballerGameweekStats.season == season,
                    FootballerGameweekStats.gameweek.in_(recent),
                )
                .group_by(FootballerGameweekStats.footballer_id)
            )
            return {footballer: total / len(recent) for footballer, total in rows.tuples()}
