"""Owner incident DMs (ticket 23): one DM per job and failure type, deduplicated.

- A failure DMs the owner when it is urgent (a 403) or the job's second failure in a row.
- While the same incident persists, at most one reminder every 6 hours (checked on each failure).
- The job's next success sends one "recovered" DM per incident that was reported.

Each DM carries a short fixed code and the job name: never a stack trace or Member details.
State is in memory: a restart forgets open incidents (a persisting one is reported again).
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from fplbot.clock import Clock
from fplbot.delivery import texts

log = logging.getLogger(__name__)

REMINDER_EVERY = timedelta(hours=6)
FAILURES_BEFORE_ALERT = 2

SendToOwner = Callable[[str], Awaitable[None]]


@dataclass
class _Incident:
    since: datetime
    last_told: datetime


class OwnerAlerts:
    def __init__(self, send: SendToOwner, clock: Clock) -> None:
        self._send = send
        self._clock = clock
        # Per job: failures in a row, and when the first of them happened.
        self._failing: dict[str, tuple[int, datetime]] = {}
        self._incidents: dict[tuple[str, str], _Incident] = {}
        self._told_once: set[tuple[str, object]] = set()

    async def job_failed(self, job: str, code: str, *, urgent: bool = False) -> None:
        now = self._clock.now()
        in_a_row, failing_since = self._failing.get(job, (0, now))
        in_a_row += 1
        self._failing[job] = (in_a_row, failing_since)
        incident = self._incidents.get((job, code))
        if incident is not None:
            if now - incident.last_told >= REMINDER_EVERY:
                incident.last_told = now
                await self._tell(code, job, texts.owner_reminder(code, job, incident.since))
            return
        if urgent or in_a_row >= FAILURES_BEFORE_ALERT:
            self._incidents[job, code] = _Incident(since=failing_since, last_told=now)
            await self._tell(code, job, texts.owner_alert(code, job))

    async def job_succeeded(self, job: str) -> None:
        self._failing.pop(job, None)
        for job_and_code in [key for key in self._incidents if key[0] == job]:
            del self._incidents[job_and_code]
            code = job_and_code[1]
            await self._tell(code, job, texts.owner_recovered(code, job))

    async def failed_once(self, job: str, code: str, period: object, text: str) -> None:
        """Tell the owner ``text`` about ``job`` failing, at most once per ``period`` (e.g. a
        night's date): for jobs that report their own failures instead of raising."""
        if (job, period) in self._told_once:
            return
        self._told_once.add((job, period))
        await self._tell(code, job, text)

    async def _tell(self, code: str, job: str, text: str) -> None:
        log.info("owner told: %s in job %s", code, job)
        try:
            await self._send(text)
        except Exception as error:  # Telegram down must not break the job
            log.error("owner DM failed: %s", type(error).__name__)
