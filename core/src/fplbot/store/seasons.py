"""FPL seasons. Every table carries a ``season`` column such as ``"2026-27"``.

The current season is explicit state (table ``seasons``), never the calendar: the bot never
rolls over by itself (ticket 40, from ticket 23).

- The first ``bootstrap-static`` the bot reads pins its season (from GW1's deadline) as current.
- A later ``bootstrap-static`` of a newer season is a *new season waiting*: it is recorded once
  (the owner gets a checklist), and ``check_bootstrap`` raises ``NewSeasonWaiting`` so that no
  job stores new-season data under the old season's key. Jobs and advice commands pause.
- The owner's confirmed ``/rollover`` (``roll_over``) makes it current, clears the tables in
  ``CLEARED_AT_ROLLOVER`` and keeps everything else under its season key.

``season_of(moment)`` stays a plain function: it reads the register that ``Seasons.load`` (at
startup) and every change keep in memory. One process owns one database, so that is enough.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from fplbot.clock import Clock
from fplbot.sources.fpl import NewSeasonWaiting
from fplbot.store.schema import (
    Base,
    Club,
    Fixture,
    FollowedLeague,
    Footballer,
    FootballerGameweekStats,
    FootballerNews,
    Gameweek,
    H2hOpponent,
    Invite,
    JobCompletion,
    LeagueStanding,
    Member,
    MemberBackupMessage,
    MemberGameweek,
    MemberLeague,
    MemberPick,
    OwnerNotice,
    PriceChange,
    PricePrediction,
    PriceSnapshot,
    RivalPick,
    Season,
    WatchedFootballer,
)

log = logging.getLogger(__name__)

# A new FPL season's game opens in July; until then the previous season is current.
_SEASON_START_MONTH = 7


def calendar_season(moment: datetime) -> str:
    """The season a moment falls in by the calendar (July to June)."""
    first_year = moment.year if moment.month >= _SEASON_START_MONTH else moment.year - 1
    return f"{first_year}-{(first_year + 1) % 100:02d}"


@dataclass(frozen=True)
class _Register:
    # Started seasons, oldest first: (started_at, season).
    starts: tuple[tuple[datetime, str], ...] = ()
    # A new season FPL shows that waits for /rollover.
    waiting: str | None = None


_register = _Register()


def season_of(moment: datetime) -> str:
    """The season current at ``moment``: the latest season started by then. Before the bot has
    pinned any season (a new database), the calendar's."""
    started = [season for at, season in _register.starts if at <= moment]
    return started[-1] if started else calendar_season(moment)


def bootstrap_season(bootstrap: Mapping[str, Any]) -> str | None:
    """The season a ``bootstrap-static`` belongs to (that of its GW1 deadline); ``None`` when it
    has no usable GW1."""
    try:
        gw1 = next(event for event in bootstrap["events"] if event.get("id") == 1)
        deadline = datetime.fromisoformat(str(gw1["deadline_time"]).replace("Z", "+00:00"))
    except KeyError, StopIteration, TypeError, ValueError, AttributeError:
        return None
    return calendar_season(deadline)


# What /rollover does with each table's rows of the season that ends. EVERY table is in exactly
# one of the two lists (a test checks): a new table must opt in or out here.
#
# Cleared (all rows not of the new season are deleted): Rival picks, Followed leagues and
# Member and Rival history (spec: "Member and Rival history is cleared at rollover").
CLEARED_AT_ROLLOVER: tuple[type[Base], ...] = (
    RivalPick,
    H2hOpponent,
    MemberLeague,
    LeagueStanding,
    FollowedLeague,
    MemberPick,
    MemberGameweek,
)
# Kept, each row under its own season key: Members and their settings (Goal, timezone, alert
# time; a Watch list's old rows simply stop counting: Footballer ids are per season), invites,
# owner bookkeeping, completion rows, and every aggregate (spec: "Kept across seasons").
KEPT_AT_ROLLOVER: tuple[type[Base], ...] = (
    Member,
    Invite,
    WatchedFootballer,
    MemberBackupMessage,
    OwnerNotice,
    JobCompletion,
    Season,
    Club,
    Footballer,
    Gameweek,
    Fixture,
    FootballerGameweekStats,
    PriceSnapshot,
    PriceChange,
    PricePrediction,
    FootballerNews,
)


@dataclass(frozen=True)
class Rollover:
    ended: str
    started: str


# Called once per new season seen, with (new season, current season): tells the owner.
type NewSeasonSeen = Callable[[str, str], Awaitable[None]]


class Seasons:
    def __init__(self, engine: AsyncEngine, clock: Clock, on_new_season: NewSeasonSeen) -> None:
        self._engine = engine
        self._clock = clock
        self._on_new_season = on_new_season

    @property
    def current(self) -> str:
        return season_of(self._clock.now())

    @property
    def waiting(self) -> str | None:
        """The new season waiting for ``/rollover``, if FPL already shows one."""
        return _register.waiting

    async def load(self) -> None:
        """Read the register from the database (at startup). A database from before seasons
        were recorded pins the latest season it has reference data for."""
        global _register
        async with self._engine.begin() as connection:
            rows = (await connection.execute(select(Season))).all()
            if not rows:
                stored = await connection.scalar(select(func.max(Gameweek.season)))
                if stored is not None:
                    now = self._clock.now()
                    await connection.execute(
                        insert(Season)
                        .values(season=stored, detected_at=now, started_at=now)
                        .on_conflict_do_nothing(index_elements=[Season.season])
                    )
                    rows = (await connection.execute(select(Season))).all()
        starts = sorted((row.started_at, row.season) for row in rows if row.started_at)
        waiting = [row.season for row in rows if row.started_at is None]
        _register = _Register(tuple(starts), max(waiting) if waiting else None)

    async def check_bootstrap(self, bootstrap: Mapping[str, Any]) -> None:
        """Called with every ``bootstrap-static`` the bot reads (``FplSource``): pins the first
        season, and raises ``NewSeasonWaiting`` for a newer one (telling the owner once)."""
        season = bootstrap_season(bootstrap)
        if season is None:
            return
        now = self._clock.now()
        if not _register.starts:
            await self._insert(season, now, started=True)
            log.info("season %s pinned as current", season)
            return
        current = season_of(now)
        if season <= current:
            return
        if _register.waiting != season and await self._insert(season, now, started=False):
            log.info("new season %s detected: waiting for /rollover", season)
            await self._on_new_season(season, current)
        raise NewSeasonWaiting

    async def roll_over(self) -> Rollover | None:
        """Start the waiting new season: clear ``CLEARED_AT_ROLLOVER`` of every other season, in
        one transaction. ``None`` (and nothing changes) when no new season is waiting, e.g. a
        second ``/rollover``."""
        waiting = _register.waiting
        if waiting is None:
            return None
        now = self._clock.now()
        ended = season_of(now)
        async with self._engine.begin() as connection:
            started = await connection.scalar(
                update(Season)
                .where(Season.season == waiting, Season.started_at.is_(None))
                .values(started_at=now)
                .returning(Season.season)
            )
            if started is not None:
                for model in CLEARED_AT_ROLLOVER:
                    table = cast(Table, model.__table__)
                    await connection.execute(delete(table).where(table.c.season != started))
        await self.load()
        if started is None:
            return None
        log.info("rolled over from season %s to %s", ended, started)
        return Rollover(ended=ended, started=started)

    async def _insert(self, season: str, now: datetime, *, started: bool) -> bool:
        """Record ``season``; ``True`` if it was new. Reloads the register."""
        async with self._engine.begin() as connection:
            inserted = await connection.scalar(
                insert(Season)
                .values(season=season, detected_at=now, started_at=now if started else None)
                .on_conflict_do_nothing(index_elements=[Season.season])
                .returning(Season.season)
            )
        await self.load()
        return inserted is not None
