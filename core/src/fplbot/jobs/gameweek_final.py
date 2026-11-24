"""The Gameweek-final job ("gw-final", ticket 32): once a Gameweek is over and checked.

FPL marks a Gameweek ``finished`` and later ``data_checked`` in ``bootstrap-static``; after
that its points and league tables no longer change. The job then:

1. (ticket 33: fetch ``event/{gw}/live`` once and store per-Gameweek Footballer stats);
2. refreshes each Member's history (``entry/{id}/history/``);
3. recomputes the Followed leagues and refreshes their tables (``jobs/followed_leagues.py``),
   which also drops leagues no Member follows any more;
4. writes the ``gw_final`` completion row of each Gameweek it covered.

It covers the last deadline's Gameweek and the one before (startup catch-up) when they are final
and have no completion row. With rows for both it does nothing at all (no FPL request).

Planning: when the stored reference data already says a missing Gameweek is final (e.g. at
startup), the job runs at once (and again hourly while it keeps failing). Otherwise it polls:
hourly, from 2 hours after the Gameweek's last kickoff (or its deadline when no fixture is
stored), each poll refreshing reference data to see whether FPL has marked it final yet.
"""

import logging
from datetime import datetime, timedelta

from fplbot.clock import Clock
from fplbot.jobs.followed_leagues import FollowedLeagues
from fplbot.jobs.runner import Job, waiting_while_updating
from fplbot.jobs.scheduler import PlannedRun
from fplbot.sources.fpl import FplSource
from fplbot.store.completions import CompletionStore, gameweek_period
from fplbot.store.members import MemberStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore

log = logging.getLogger(__name__)

GW_FINAL_JOB = "gw-final"  # the name the owner sees
GW_FINAL_COMPLETION = "gw_final"  # the completion row's job
POLL_EVERY = timedelta(hours=1)
POLL_AFTER_LAST_KICKOFF = timedelta(hours=2)
# A poll reuses a bootstrap-static fetched this recently.
JUST_FETCHED = timedelta(minutes=5)


class GameweekFinal:
    def __init__(
        self,
        *,
        clock: Clock,
        members: MemberStore,
        reference: ReferenceStore,
        squads: SquadStore,
        completions: CompletionStore,
        followed_leagues: FollowedLeagues,
    ) -> None:
        self._clock = clock
        self._members = members
        self._reference = reference
        self._squads = squads
        self._completions = completions
        self._followed_leagues = followed_leagues

    async def plan(self, now: datetime) -> list[PlannedRun]:
        """Planner (``Scheduler.add``)."""
        missing = await self._missing(now)
        if not missing:
            return []
        season = season_of(now)
        final = [gw for gw in missing if await self._is_final(season, gw)]
        if final:
            # Keyed by the hour: a run that failed (e.g. a 403) is tried again an hour later.
            key = f"gw-final@gw{max(final)}@{now:%Y-%m-%dT%H}"
            return [PlannedRun(at=now, name=GW_FINAL_JOB, job=self.job(), key=key)]
        latest = max(missing)
        kickoff = await self._reference.last_kickoff(season, latest)
        if kickoff is None:
            info = await self._reference.gameweek(season, latest)
            kickoff = info.deadline if info else now
        return [
            PlannedRun(
                at=_next_hour(max(now, kickoff + POLL_AFTER_LAST_KICKOFF)),
                name=GW_FINAL_JOB,
                job=self.job(refresh=True),
            )
        ]

    def job(self, *, refresh: bool = False) -> Job:
        """The job; ``refresh`` first re-reads reference data to see whether FPL has marked the
        Gameweek final yet (a poll)."""

        async def job(fpl: FplSource) -> None:
            now = self._clock.now()
            season = season_of(now)
            if not await self._missing(now):
                return
            if refresh:
                await self._reference.refresh(fpl, max_age=JUST_FETCHED)
            final = [gw for gw in await self._missing(now) if await self._is_final(season, gw)]
            if not final:
                return
            # Ticket 33: fetch event/{gw}/live once for each Gameweek in ``final`` here.
            for member_number, team_id in await self._members.linked_teams():
                history = await fpl.history(team_id)
                if history is not None:
                    await self._squads.save_history(member_number, season, history)
            await self._followed_leagues.recompute(fpl)
            for gameweek in final:
                period = gameweek_period(gameweek)
                await self._completions.record(GW_FINAL_COMPLETION, season, period, now)
            log.info("gameweek %d final: history and league tables refreshed", max(final))

        return waiting_while_updating(job, self._clock)

    async def _missing(self, now: datetime) -> list[int]:
        """The last deadline's Gameweek and the one before, where they have no completion row."""
        last = (await self._reference.deadlines(now)).last
        if last is None:
            return []
        candidates = [gw for gw in (last.id - 1, last.id) if gw >= 1]
        done = await self._completions.done_periods(
            GW_FINAL_COMPLETION, season_of(now), (gameweek_period(gw) for gw in candidates)
        )
        return [gw for gw in candidates if gameweek_period(gw) not in done]

    async def _is_final(self, season: str, gameweek: int) -> bool:
        info = await self._reference.gameweek(season, gameweek)
        return info is not None and info.final


def _next_hour(moment: datetime) -> datetime:
    """``moment`` if it is on the hour, else the next whole hour."""
    whole = moment.replace(minute=0, second=0, microsecond=0)
    return whole if whole == moment else whole + timedelta(hours=1)
