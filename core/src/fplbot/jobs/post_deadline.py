"""The post-deadline job and the reference-data refreshes around each deadline (ticket 31).

Post-deadline job ("picks"), per Gameweek, from deadline +5 minutes:

1. one cheap probe (``event-status/``); while FPL answers "The game is being updated", wait
   10 minutes and start again (``waiting_while_updating``; not counted as backoff tries);
2. refresh reference data, as the "just after the deadline" ``bootstrap-static`` fetch;
3. the Elite cohort's standings pages (ticket 34), before any picks, when the Elite sample is
   due (``EliteSampler.due``: the last deadline's Gameweek, still being played);
4. each Member's locked Squad for the Gameweek;
5. the Rivals' Squads (ticket 33), when the Gameweek is the last deadline's;
6. the ``picks`` completion row for the Gameweek;
7. the Elite picks sample, with its own ``elite`` completion row.

Steps 3 and 7 run as the job "elite" (``jobs/elite.py``): their failure is reported under that
name and never stops the Members' picks. The job is idempotent: with both completion rows it
does nothing (no FPL request, no message); with only ``picks`` it does just the Elite steps.
Planning (``plan``) runs it at next deadline +5 minutes, and at once for the last and previous
Gameweek if either has no completion row yet (or the last one is missing its due Elite sample):
that is the startup catch-up. A run that fails (e.g. a 403) is not retried until its next
planned run (the next deadline, or a restart).

Reference refreshes ("reference"): once at startup, and at deadline -90 and -30 minutes.
"""

import logging
from datetime import datetime, timedelta

from fplbot.clock import Clock
from fplbot.jobs.elite import EliteSampler
from fplbot.jobs.rival_picks import RivalPicks
from fplbot.jobs.runner import Job, waiting_while_updating
from fplbot.jobs.scheduler import PlannedRun
from fplbot.sources.fpl import FplSource
from fplbot.store.completions import CompletionStore, gameweek_period
from fplbot.store.members import MemberStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore

log = logging.getLogger(__name__)

PICKS_JOB = "picks"
REFERENCE_JOB = "reference"
AFTER_DEADLINE = timedelta(minutes=5)
REFRESH_BEFORE_DEADLINE = (timedelta(minutes=90), timedelta(minutes=30))
PROBE_PATH = "event-status/"
# The post-deadline job reuses a bootstrap-static fetched this recently (e.g. at startup).
JUST_FETCHED = timedelta(minutes=5)
STARTUP_GRACE = timedelta(days=1)


class PostDeadline:
    def __init__(
        self,
        *,
        clock: Clock,
        members: MemberStore,
        reference: ReferenceStore,
        squads: SquadStore,
        completions: CompletionStore,
        rival_picks: RivalPicks,
        elite: EliteSampler | None = None,
    ) -> None:
        self._clock = clock
        self._elite = elite
        self._rival_picks = rival_picks
        self._members = members
        self._reference = reference
        self._squads = squads
        self._completions = completions
        self._started_at: datetime | None = None

    async def plan(self, now: datetime) -> list[PlannedRun]:
        """Planner (``Scheduler.add``): picks runs and reference refreshes."""
        if self._started_at is None:
            self._started_at = now
        runs = [
            PlannedRun(
                at=self._started_at,
                name=REFERENCE_JOB,
                job=self.refresh_job(),
                key="reference@startup",
                grace=STARTUP_GRACE,
            )
        ]
        deadlines = await self._reference.deadlines(now)
        if deadlines.next is not None:
            runs.extend(
                PlannedRun(
                    at=deadlines.next.deadline - before, name=REFERENCE_JOB, job=self.refresh_job()
                )
                for before in REFRESH_BEFORE_DEADLINE
            )
        due: dict[int, datetime] = {}
        if deadlines.next is not None:
            due[deadlines.next.id] = deadlines.next.deadline + AFTER_DEADLINE
        if deadlines.last is not None:
            due[deadlines.last.id] = max(deadlines.last.deadline + AFTER_DEADLINE, now)
            if deadlines.last.id > 1:
                due[deadlines.last.id - 1] = now
        done = await self._completions.done_periods(
            PICKS_JOB, season_of(now), (gameweek_period(gw) for gw in due)
        )
        for gw, at in due.items():
            if gameweek_period(gw) not in done or await self._elite_due(gw):
                runs.append(
                    PlannedRun(at=at, name=PICKS_JOB, job=self.picks_job(gw), key=f"picks@gw{gw}")
                )
        return runs

    def refresh_job(self) -> Job:
        async def job(fpl: FplSource) -> None:
            await self._reference.refresh(fpl, max_age=timedelta(0))

        return waiting_while_updating(job, self._clock)

    def picks_job(self, gameweek: int) -> Job:
        """Store every Member's Squad at ``gameweek``'s deadline, then the completion row; and
        the Elite sample around them when it is due (see the module docstring)."""
        period = gameweek_period(gameweek)

        async def job(fpl: FplSource) -> None:
            season = season_of(self._clock.now())
            picks_done = await self._completions.done(PICKS_JOB, season, period)
            if picks_done and not await self._elite_due(gameweek):
                return
            await fpl.get_json(PROBE_PATH)
            await self._reference.refresh(fpl, max_age=JUST_FETCHED)
            # The Elite cohort: read first, aiming to finish before the first kickoff. A failed
            # read leaves this Gameweek without Elite figures, never without Members' picks.
            cohort = None
            if self._elite is not None and await self._elite.due(gameweek):
                cohort = await self._elite.read_cohort(gameweek)
            if not picks_done:
                await self._member_and_rival_picks(fpl, season, gameweek)
                await self._completions.record(PICKS_JOB, season, period, self._clock.now())
                log.info("picks stored for gameweek %d", gameweek)
            if self._elite is not None and cohort is not None:
                await self._elite.sample(cohort)

        return waiting_while_updating(job, self._clock)

    async def _member_and_rival_picks(self, fpl: FplSource, season: str, gameweek: int) -> None:
        for member_number, team_id in await self._members.linked_teams():
            picks = await fpl.picks(team_id, gameweek)
            if picks is None:
                continue  # no Squad at that deadline (team created later): /squad explains
            await self._squads.save_picks(member_number, season, picks)
        # Rival picks (ticket 33), only for the Gameweek the Rival gap compares: a catch-up run
        # for the Gameweek before it skips them.
        last = (await self._reference.deadlines(self._clock.now())).last
        if last is not None and last.id == gameweek:
            await self._rival_picks.fetch_missing(fpl, season, gameweek)

    async def _elite_due(self, gameweek: int) -> bool:
        return self._elite is not None and await self._elite.due(gameweek)
