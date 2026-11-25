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
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fplbot.advice.elite import EliteTally, Stratum, sample_size_for
from fplbot.advice.elite import figures as elite_figures
from fplbot.clock import Clock
from fplbot.jobs.runner import JobRunner, waiting_while_updating
from fplbot.sources.fpl import (
    STANDINGS_PAGE_SIZE,
    FplSource,
    FplError,
    FplStandings,
    FplUnexpectedStatus,
    FplUpdating,
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
    """The top cohort: the first ``size`` managers of the overall league, all read, and a simple
    random sample of ``target`` of them."""

    name: str  # "10k": how /gap and the stored rows name it
    size: int
    target: int  # the sample size aimed for


@dataclass(frozen=True)
class WiderCohort:
    """A cohort reaching deeper than the top one (the top 100k), estimated from two strata
    (research 03): the top cohort's own sample, and ranks ``top.size + 1`` to ``size``, read as
    ``pages`` random standings pages of those ranks with ``per_page`` random managers each."""

    name: str  # "100k"
    size: int
    pages: int
    per_page: int


TOP_10K = EliteCohort("10k", size=10_000, target=sample_size_for(10_000, 0.02))
# 250 of pages 201-2000, 8 managers each: 2,000 Squads, which with the top 10k's 1,937 gives
# ±2.0% on the top 100k. With the 200 top-10k pages, 450 standings pages in all.
TOP_100K = WiderCohort("100k", size=100_000, pages=250, per_page=8)


@dataclass(frozen=True)
class EliteDesign:
    cohort: EliteCohort = TOP_10K
    wider: WiderCohort | None = TOP_100K
    draw: Draw = field(default=random_draw)


# Production: the top 10k and the top 100k at ±2%, drawn at random.
ELITE_DESIGN = EliteDesign()


@dataclass(frozen=True)
class Cohort:
    """The cohorts as read for one run. In memory only, gone when the run ends."""

    gameweek: int
    entries: tuple[int, ...]  # the whole top cohort
    deeper: tuple[int, ...]  # the wider cohort's second stratum, already drawn


@dataclass
class _Stratum:
    size: int  # managers in the stratum
    remaining: deque[int]  # drawn managers whose Squad is still to read
    target: int
    tally: EliteTally = field(default_factory=EliteTally)


@dataclass
class _Estimate:
    name: str
    strata: tuple[_Stratum, ...]
    saved: bool = False

    @property
    def finished(self) -> bool:
        return all(not stratum.remaining for stratum in self.strata)


def _half_way(stratum: _Stratum) -> bool:
    return stratum.tally.size > 0 and 2 * stratum.tally.size >= stratum.target


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
        """Read the standings pages that fix the cohorts (and draw the wider cohort's second
        stratum); ``None`` if that failed (the owner is told as for any job, and the Gameweek
        gets no Elite figures from this run)."""
        read: list[Cohort] = []
        design = self._design
        top = design.cohort

        async def job(fpl: FplSource) -> None:
            pages: dict[int, FplStandings] = {}

            async def page(number: int) -> FplStandings:
                if number not in pages:
                    table = await fpl.standings("classic", OVERALL_LEAGUE, number)
                    if table is None:
                        raise FplUnexpectedStatus(404)
                    pages[number] = table
                return pages[number]

            entries: list[int] = []
            for number in range(1, math.ceil(top.size / STANDINGS_PAGE_SIZE) + 1):
                table = await page(number)
                entries += [row.entry_id for row in table.rows if row.position <= top.size]
                if not table.has_next:
                    break
            deeper: list[int] = []
            wider = design.wider
            if wider is not None:
                numbers = range(
                    top.size // STANDINGS_PAGE_SIZE + 1,
                    math.ceil(wider.size / STANDINGS_PAGE_SIZE) + 1,
                )
                for number in design.draw(numbers, min(wider.pages, len(numbers))):
                    rows = [
                        row.entry_id
                        for row in (await page(number)).rows
                        if top.size < row.position <= wider.size
                    ]
                    deeper += design.draw(rows, min(wider.per_page, len(rows)))
            read.append(Cohort(gameweek, tuple(entries), tuple(deeper)))

        await self._jobs.run(ELITE_JOB, waiting_while_updating(job, self._clock), Priority.ELITE)
        return read[0] if read else None

    async def sample(self, cohort: Cohort) -> None:
        """Sample the cohorts' Squads at the Gameweek's deadline and store the shares: the top
        cohort's stratum first, stored as soon as it is done, then the wider cohort's second."""
        design = self._design
        period = gameweek_period(cohort.gameweek)
        top = _Stratum(
            size=len(cohort.entries),
            remaining=deque(
                design.draw(cohort.entries, min(design.cohort.target, len(cohort.entries)))
            ),
            target=min(design.cohort.target, len(cohort.entries)),
        )
        estimates = [_Estimate(design.cohort.name, (top,))]
        if design.wider is not None:
            deeper = _Stratum(
                size=design.wider.size - design.cohort.size,
                remaining=deque(cohort.deeper),
                target=len(cohort.deeper),
            )
            estimates.append(_Estimate(design.wider.name, (top, deeper)))
        strata = [estimate.strata[-1] for estimate in estimates]

        async def job(fpl: FplSource) -> None:
            season = season_of(self._clock.now())
            if await self._completions.done(ELITE_JOB, season, period):
                return
            try:
                for stratum in strata:
                    while stratum.remaining:
                        squad = await fpl.picks(stratum.remaining[0], cohort.gameweek)
                        stratum.remaining.popleft()
                        if squad is not None:  # hidden or absent: the sample is one smaller
                            stratum.tally.add(squad)
                    for estimate in estimates:
                        if estimate.finished and not estimate.saved:
                            await self._save(season, cohort, estimate)
            except FplUpdating:
                raise  # waited out, then resumed where it stopped (the tallies are kept)
            except FplError:
                # The run stops here. A cohort whose every stratum reached half its target is
                # published as a partial sample; any other keeps last Gameweek's figures.
                for estimate in estimates:
                    if not estimate.saved and all(_half_way(s) for s in estimate.strata):
                        await self._save(season, cohort, estimate, partial=True)
                raise
            now = self._clock.now()
            await self._completions.record(ELITE_JOB, season, period, now)

        await self._jobs.run(ELITE_JOB, waiting_while_updating(job, self._clock), Priority.ELITE)

    async def _save(
        self, season: str, cohort: Cohort, estimate: _Estimate, *, partial: bool = False
    ) -> None:
        if any(stratum.tally.size == 0 for stratum in estimate.strata):
            raise FplUnexpectedStatus(404)  # not one sampled Squad of a stratum could be read
        strata = [Stratum(s.tally, s.size, s.target) for s in estimate.strata]
        figures = elite_figures(estimate.name, cohort.gameweek, strata, partial=partial)
        if partial:
            # A rerun that stops early never replaces a full sample or a bigger partial one.
            stored = await self._store.figures(season, cohort.gameweek, estimate.name)
            if stored is not None and (
                not stored.partial or stored.sample_size >= figures.sample_size
            ):
                return
        await self._store.save(season, figures, self._clock.now())
        estimate.saved = True
        log.info(
            "elite %s sample stored for gameweek %d: %d of %d",
            estimate.name,
            cohort.gameweek,
            figures.sample_size,
            figures.cohort_size,
        )
