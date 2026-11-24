"""The Elite sampler (ticket 34): our own sample of the top 10k, on the official API.

Run by the post-deadline job (``jobs/post_deadline.py``) for the last deadline's Gameweek while
it is being played, in two steps reported to the owner as the job "elite":

1. ``read_cohort``: the overall league's standings pages that fix the cohort (the first 10,000
   managers in FPL's order: 200 pages of 50), before the Members' picks, aiming to finish
   before the first kickoff;
2. ``sample``, after the Members' and Rivals' picks: a simple random sample of the cohort sized
   for ±2% at 95% (1,937 managers), one picks request each, tallied into shares
   (``advice/elite.py``) and stored as aggregates only (``store/elite.py``), then the ``elite``
   completion row.

Every request runs at ``Priority.ELITE``, the lowest of the shared limiter: interactive
commands, the Price alert and routine jobs go first. The cohort's entry IDs live in memory for
the length of one run; a sampled Squad only bumps counters. Neither is ever stored or logged.

``EliteDesign`` is injectable so tests can run the sampler at a small scale (a cohort of one
standings page, a deterministic draw).
"""

import logging
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fplbot.advice.elite import EliteTally, sample_size_for
from fplbot.clock import Clock
from fplbot.jobs.runner import JobRunner, waiting_while_updating
from fplbot.sources.fpl import (
    STANDINGS_PAGE_SIZE,
    FplSource,
    FplUnexpectedStatus,
    Priority,
)
from fplbot.store.completions import CompletionStore, gameweek_period
from fplbot.store.elite import EliteStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)

ELITE_JOB = "elite"
OVERALL_LEAGUE = 314  # FPL's "Overall" classic league: every team, in overall-rank order

# Picks ``n`` of the cohort's entries (in FPL's order), without replacement.
type Draw = Callable[[Sequence[int], int], Sequence[int]]


def random_draw(entries: Sequence[int], n: int) -> Sequence[int]:
    return random.SystemRandom().sample(entries, n)


@dataclass(frozen=True)
class EliteCohort:
    name: str  # "10k": how /gap and the stored rows name it
    size: int  # the first ``size`` managers of the overall league
    target: int  # the sample size aimed for


TOP_10K = EliteCohort("10k", size=10_000, target=sample_size_for(10_000, 0.02))


@dataclass(frozen=True)
class EliteDesign:
    cohort: EliteCohort = TOP_10K
    draw: Draw = field(default=random_draw)


# Production: the top 10k at ±2%, drawn at random.
ELITE_DESIGN = EliteDesign()


@dataclass(frozen=True)
class Cohort:
    """The cohort as read for one run. In memory only, gone when the run ends."""

    gameweek: int
    entries: tuple[int, ...]


class EliteSampler:
    def __init__(
        self,
        *,
        design: EliteDesign,
        clock: Clock,
        reference: ReferenceStore,
        store: EliteStore,
        completions: CompletionStore,
        jobs: JobRunner,
    ) -> None:
        self._design = design
        self._clock = clock
        self._reference = reference
        self._store = store
        self._completions = completions
        self._jobs = jobs

    async def due(self, gameweek: int) -> bool:
        """Whether ``gameweek`` still needs its sample: it is the last deadline's Gameweek, not
        finished yet (no Elite backfill of past Gameweeks) and has no ``elite`` row."""
        now = self._clock.now()
        last = (await self._reference.deadlines(now)).last
        if last is None or last.id != gameweek or last.finished:
            return False
        return not await self._completions.done(
            ELITE_JOB, season_of(now), gameweek_period(gameweek)
        )

    async def read_cohort(self, gameweek: int) -> Cohort | None:
        """Read the standings pages that fix the cohort; ``None`` if that failed (the owner is
        told as for any job, and the Gameweek gets no Elite figures from this run)."""
        read: list[Cohort] = []
        cohort = self._design.cohort

        async def job(fpl: FplSource) -> None:
            entries: list[int] = []
            for page in range(1, math.ceil(cohort.size / STANDINGS_PAGE_SIZE) + 1):
                table = await fpl.standings("classic", OVERALL_LEAGUE, page)
                if table is None:
                    raise FplUnexpectedStatus(404)
                entries += [row.entry_id for row in table.rows if row.position <= cohort.size]
                if not table.has_next:
                    break
            read.append(Cohort(gameweek, tuple(entries)))

        await self._jobs.run(ELITE_JOB, waiting_while_updating(job, self._clock), Priority.ELITE)
        return read[0] if read else None

    async def sample(self, cohort: Cohort) -> None:
        """Sample the cohort's Squads at the Gameweek's deadline and store the shares."""
        design = self._design
        period = gameweek_period(cohort.gameweek)

        async def job(fpl: FplSource) -> None:
            season = season_of(self._clock.now())
            if await self._completions.done(ELITE_JOB, season, period):
                return
            target = min(design.cohort.target, len(cohort.entries))
            tally = EliteTally()
            for entry in design.draw(cohort.entries, target):
                squad = await fpl.picks(entry, cohort.gameweek)
                if squad is not None:  # hidden or absent: the sample is one smaller
                    tally.add(squad)
            if tally.size == 0:
                raise FplUnexpectedStatus(404)  # not one sampled Squad could be read
            figures = tally.figures(
                design.cohort.name,
                cohort.gameweek,
                cohort_size=len(cohort.entries),
                target_size=target,
            )
            now = self._clock.now()
            await self._store.save(season, figures, now)
            await self._completions.record(ELITE_JOB, season, period, now)
            log.info(
                "elite sample stored for gameweek %d: %d of %d",
                cohort.gameweek,
                tally.size,
                len(cohort.entries),
            )

        await self._jobs.run(ELITE_JOB, waiting_while_updating(job, self._clock), Priority.ELITE)
