"""Reference data kept across seasons: clubs, Footballers, Gameweeks and fixtures.

``refresh`` reads ``bootstrap-static`` (through the in-memory copy ``FplSource`` keeps) and
``fixtures/``, and writes only rows that changed, so a refresh with nothing new costs Neon no
writes. Raw FPL responses are never stored.

Interactive commands read what is stored and only fetch when nothing is stored for the season
yet (``ensure_loaded``); scheduled refreshes (ticket 31) and the join backfill keep it current.

Gameweek timing is derived from stored deadlines and the clock, not from FPL's
``is_current``/``is_next`` flags (which lag while FPL updates): see ``deadlines``.
"""

import asyncio
import logging
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Table, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fplbot.clock import Clock
from fplbot.sources.fpl import BOOTSTRAP_MAX_AGE, FplError, FplSource
from fplbot.store.schema import Club, Fixture, Footballer, Gameweek
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameweekInfo:
    id: int
    deadline: datetime
    finished: bool
    data_checked: bool = False

    @property
    def final(self) -> bool:
        """FPL has finished and checked the Gameweek: its points and tables won't change."""
        return self.finished and self.data_checked


@dataclass(frozen=True)
class Deadlines:
    """Where ``now`` sits in the season."""

    # The latest Gameweek whose deadline has passed: its picks are public. None before GW1.
    last: GameweekInfo | None
    # The next deadline: picks for it stay hidden until then. None after the last Gameweek.
    next: GameweekInfo | None


class ReferenceStore:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._clock = clock
        self._lock = asyncio.Lock()

    async def refresh(self, fpl: FplSource, max_age: timedelta = BOOTSTRAP_MAX_AGE) -> None:
        """Fetch ``bootstrap-static`` (unless the in-memory copy is younger than ``max_age``;
        pass ``timedelta(0)`` to force it) and ``fixtures/``, and store what changed. Raises
        ``FplError`` when FPL fails, for the job runner to report."""
        async with self._lock:
            reference = await fpl.reference(max_age)
            fixtures = await fpl.fixtures()
            season = season_of(self._clock.now())
            async with self._sessions.begin() as session:
                await _upsert(session, Club, season, (asdict(c) for c in reference.clubs))
                await _upsert(
                    session, Footballer, season, (asdict(f) for f in reference.footballers)
                )
                await _upsert(session, Gameweek, season, (asdict(g) for g in reference.gameweeks))
                await _upsert(session, Fixture, season, (asdict(f) for f in fixtures))

    async def ensure_loaded(self, fpl: FplSource) -> None:
        """For interactive commands: fetch reference data only if none is stored for this
        season. Fail-soft: if FPL fails, callers see what is (not) stored."""
        season = season_of(self._clock.now())
        async with self._sessions() as session:
            stored = await session.scalar(select(Gameweek.id).where(Gameweek.season == season))
        if stored is not None:
            return
        try:
            await self.refresh(fpl)
        except FplError as error:
            log.info("reference data refresh failed: %s", error.code)

    async def deadlines(self, now: datetime) -> Deadlines:
        """The last passed and the next deadline of ``now``'s season."""
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Gameweek)
                .where(Gameweek.season == season_of(now))
                .order_by(Gameweek.deadline)
            )
            gameweeks = [GameweekInfo(g.id, g.deadline, g.finished, g.data_checked) for g in rows]
        passed = [g for g in gameweeks if g.deadline <= now]
        upcoming = [g for g in gameweeks if g.deadline > now]
        return Deadlines(
            last=passed[-1] if passed else None, next=upcoming[0] if upcoming else None
        )

    async def gameweeks(self, season: str) -> list[GameweekInfo]:
        """Every stored Gameweek of ``season``, in order."""
        async with self._sessions() as session:
            rows = await session.scalars(
                select(Gameweek).where(Gameweek.season == season).order_by(Gameweek.id)
            )
            return [GameweekInfo(g.id, g.deadline, g.finished, g.data_checked) for g in rows]

    async def gameweek(self, season: str, gameweek: int) -> GameweekInfo | None:
        async with self._sessions() as session:
            g = await session.get(Gameweek, (season, gameweek))
        return None if g is None else GameweekInfo(g.id, g.deadline, g.finished, g.data_checked)

    async def footballer_names(self, season: str, ids: Iterable[int]) -> dict[int, str]:
        """The FPL short name (``web_name``) of each of ``ids`` that is stored."""
        wanted = list(ids)
        async with self._sessions() as session:
            rows = await session.execute(
                select(Footballer.id, Footballer.web_name).where(
                    Footballer.season == season, Footballer.id.in_(wanted)
                )
            )
            return dict(rows.tuples().all())

    async def last_kickoff(self, season: str, gameweek: int) -> datetime | None:
        """The latest stored kickoff of ``gameweek``'s fixtures, or None if none is stored."""
        async with self._sessions() as session:
            return await session.scalar(
                select(func.max(Fixture.kickoff)).where(
                    Fixture.season == season, Fixture.gameweek == gameweek
                )
            )


async def _upsert(
    session: AsyncSession, model: Any, season: str, rows: Iterable[Mapping[str, Any]]
) -> None:
    """Insert ``rows`` into ``model``'s table for ``season``; update existing rows only where a
    value differs."""
    values = [{"season": season, **_columns(model, row)} for row in rows]
    if not values:
        return
    table: Table = model.__table__
    keys = [column.name for column in table.primary_key.columns]
    others = [column.name for column in table.columns if column.name not in keys]
    statement = insert(table).values(values)
    excluded = statement.excluded
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=keys,
            set_={name: excluded[name] for name in others},
            where=or_(*(table.c[name].is_distinct_from(excluded[name]) for name in others)),
        )
    )


def _columns(model: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    """The fields of an FPL dataclass that are columns of ``model``'s table."""
    table: Table = model.__table__
    return {name: value for name, value in row.items() if name in table.c}
