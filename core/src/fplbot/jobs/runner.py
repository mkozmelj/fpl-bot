"""Runs jobs and reports their outcome to the owner.

A job is an async function given an ``FplSource`` at the job's priority. A job that raises
``FplError`` (or anything else) has failed: the error ends the run, so after a 403 the job does
no more FPL requests until its next scheduled run. Outcomes go to ``OwnerAlerts``, which decides
whether the owner is told. Logs carry the job name and fixed code only.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fplbot.delivery.owner_alerts import OwnerAlerts
from fplbot.sources.fpl import FplBlocked, FplError, FplSource, Priority

log = logging.getLogger(__name__)

Job = Callable[[FplSource], Awaitable[None]]
JOB_ERROR = "JOB-ERROR"


class JobRunner:
    def __init__(self, fpl: FplSource, alerts: OwnerAlerts) -> None:
        self._fpl = fpl
        self._alerts = alerts
        # Jobs running in the background; the test harness waits on these.
        self.running: set[asyncio.Task[bool]] = set()

    def start(self, name: str, job: Job, priority: Priority) -> asyncio.Task[bool]:
        """Run ``job`` in the background."""
        task = asyncio.create_task(self.run(name, job, priority), name=f"job {name}")
        self.running.add(task)
        task.add_done_callback(self.running.discard)
        return task

    async def run(self, name: str, job: Job, priority: Priority) -> bool:
        """Run ``job`` to completion; ``True`` if it succeeded."""
        try:
            await job(self._fpl.with_priority(priority))
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
