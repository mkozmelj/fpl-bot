"""Join backfill (spec, launch backfill): once a Member links their team, fetch reference data,
their season history and the Squad they picked at every deadline so far.

Runs as a background job at routine priority so it never holds up anyone's conversation. If the
Member leaves while it runs, it stops at the next write. Logs name the Member by number only.
"""

import logging

from fplbot.clock import Clock
from fplbot.jobs.runner import Job
from fplbot.sources.fpl import FplSource
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore

log = logging.getLogger(__name__)

JOB_NAME = "backfill"


def backfill_member(
    member_number: int,
    team_id: int,
    *,
    reference: ReferenceStore,
    squads: SquadStore,
    clock: Clock,
) -> Job:
    async def job(fpl: FplSource) -> None:
        await reference.refresh(fpl)
        season = season_of(clock.now())
        history = await fpl.history(team_id)
        if history is None:
            log.info("member %d has no FPL history to backfill", member_number)
            return
        if not await squads.save_history(member_number, season, history):
            return
        for gameweek in history.gameweeks:
            picks = await fpl.picks(team_id, gameweek.gameweek)
            if picks is None:
                continue  # hidden or missing: /squad explains
            if not await squads.save_picks(member_number, season, picks):
                return
        log.info("member %d backfilled", member_number)

    return job
