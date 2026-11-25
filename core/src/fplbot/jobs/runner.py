"""Runs jobs and reports their outcome to the owner.

A job is an async function given an ``FplSource`` at the job's priority. A job that raises
``FplError`` (or anything else) has failed: the error ends the run, so after a 403 the job does
no more FPL requests until its next scheduled run. Outcomes go to ``OwnerAlerts``, which decides
whether the owner is told. Logs carry the job name and fixed code only.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from fplbot.clock import Clock
from fplbot.delivery.owner_alerts import OwnerAlerts
from fplbot.sources.fpl import (
    FplBlocked,
    FplError,
    FplSource,
    FplUpdating,
    NewSeasonWaiting,
    Priority,
)

log = logging.getLogger(__name__)

Job = Callable[[FplSource], Awaitable[None]]
JOB_ERROR = "JOB-ERROR"


UPDATING_WAIT = timedelta(minutes=10)
# After a deadline FPL is usually "updating" for 20-60 minutes; past this, report the job failed.
UPDATING_GIVE_UP_AFTER = timedelta(hours=6)


def waiting_while_updating(job: Job, clock: Clock) -> Job:
    """``job``, restarted from the top every 10 minutes while FPL answers "The game is being
    updated" (spec: these waits are not backoff tries). The job must be idempotent."""

    async def patient(fpl: FplSource) -> None:
        give_up = clock.now() + UPDATING_GIVE_UP_AFTER
        while True:
            try:
                await job(fpl)
                return
            except FplUpdating:
                if clock.now() + UPDATING_WAIT > give_up:
                    raise
                log.info("fpl is updating, trying again in 10 minutes")
                await clock.sleep(UPDATING_WAIT.total_seconds())

    return patient


class JobRunner:
    def __init__(
        self, fpl: FplSource, alerts: OwnerAlerts, paused: Callable[[str], bool] = lambda _: False
    ) -> None:
        self._fpl = fpl
        self._alerts = alerts
        # Whether a job (by name) must not run now: while a new season waits for /rollover.
        self._paused = paused
        # Jobs running in the background; the test harness waits on these.
        self.running: set[asyncio.Task[bool]] = set()

    def start(self, name: str, job: Job, priority: Priority) -> asyncio.Task[bool]:
        """Run ``job`` in the background."""
        task = asyncio.create_task(self.run(name, job, priority), name=f"job {name}")
        self.running.add(task)
        task.add_done_callback(self.running.discard)
        return task

    async def run(self, name: str, job: Job, priority: Priority) -> bool:
        """Run ``job`` to completion; ``True`` if it succeeded. A paused job does not run."""
        if self._paused(name):
            log.info("job %s paused: a new season waits for /rollover", name)
            return False
        try:
            await job(self._fpl.with_priority(priority))
        except NewSeasonWaiting:
            # Not a failure: the owner already has the new-season checklist.
            log.info("job %s stopped: a new season waits for /rollover", name)
            return False
        except FplError as error:
            log.warning("job %s failed: %s", name, error.code)
            await self._alerts.job_failed(name, error.code, urgent=isinstance(error, FplBlocked))
            return False
        except Exception as error:
            log.error("job %s failed: %s", name, type(error).__name__)
            await self._alerts.job_failed(name, JOB_ERROR)
            return False
        await self._alerts.job_succeeded(name)
        return True
