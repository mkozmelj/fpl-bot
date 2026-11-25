"""Per-Gameweek Footballer stats (ticket 33): ``event/{gw}/live/``, read once per Gameweek.

The Gameweek-final job reads it first for each Gameweek it covers (``fetch``). A launch backfill
(the planner ``plan``, job "footballer-stats") reads it for every finished and checked Gameweek
of the season that has none yet: at startup, and again an hour later while it keeps failing.
Each Gameweek read gets a ``gw_stats`` completion row, so it is never read twice; with rows for
every final Gameweek the planner plans nothing and no request is made.
"""

import asyncio
import logging
from datetime import datetime

from fplbot.clock import Clock
from fplbot.jobs.runner import Job, waiting_while_updating
from fplbot.jobs.scheduler import PlannedRun
from fplbot.sources.fpl import FplSource
from fplbot.store.completions import CompletionStore, gameweek_period
from fplbot.store.footballer_stats import FootballerStatsStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)

STATS_JOB = "footballer-stats"  # the name the owner sees
STATS_COMPLETION = "gw_stats"  # the completion row's job


class FootballerStats:
    def __init__(
        self,
        *,
        clock: Clock,
        reference: ReferenceStore,
        stats: FootballerStatsStore,
        completions: CompletionStore,
    ) -> None:
        self._clock = clock
        self._reference = reference
        self._stats = stats
        self._completions = completions
        # The Gameweek-final job and the backfill may want the same Gameweek at once.
        self._lock = asyncio.Lock()

    async def fetch(self, fpl: FplSource, season: str, gameweek: int) -> None:
        """Read and store ``gameweek``'s stats unless already done. Raises ``FplError``."""
        period = gameweek_period(gameweek)
        async with self._lock:
            if await self._completions.done(STATS_COMPLETION, season, period):
                return
            footballers = await fpl.live(gameweek)
            if footballers is not None:  # 404: FPL has nothing for it, nothing will come
                await self._stats.save(season, gameweek, footballers)
            await self._completions.record(STATS_COMPLETION, season, period, self._clock.now())

    async def plan(self, now: datetime) -> list[PlannedRun]:
        """Planner (``Scheduler.add``): the backfill, when a final Gameweek has no stats."""
        if not await self._missing(season_of(now)):
            return []
        # Keyed by the hour: a run that failed (e.g. a 403) is tried again an hour later.
        key = f"{STATS_JOB}@{now:%Y-%m-%dT%H}"
        return [PlannedRun(at=now, name=STATS_JOB, job=self.backfill_job(), key=key)]

    def backfill_job(self) -> Job:
        async def job(fpl: FplSource) -> None:
            season = season_of(self._clock.now())
            missing = await self._missing(season)
            for gameweek in missing:
                await self.fetch(fpl, season, gameweek)
            if missing:
                log.info("footballer stats stored for %d gameweeks", len(missing))

        return waiting_while_updating(job, self._clock)

    async def _missing(self, season: str) -> list[int]:
        final = [g.id for g in await self._reference.gameweeks(season) if g.final]
        done = await self._completions.done_periods(
            STATS_COMPLETION, season, (gameweek_period(gw) for gw in final)
        )
        return [gw for gw in final if gameweek_period(gw) not in done]
