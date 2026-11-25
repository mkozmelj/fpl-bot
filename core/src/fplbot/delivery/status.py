"""The owner's ``/status`` (ticket 23): read-only, owner-only.

Uptime and deploy version, the last completion of each ingestion job, whether Neon answers and
the database size. Compute hours need a Neon API key, so they are not read (see store/usage.py).
"""

import logging
from datetime import datetime, timedelta

from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.store.completions import CompletionStore
from fplbot.store.usage import DatabaseUsage

log = logging.getLogger(__name__)

STATUS_JOBS = ("price_archive", "picks", "elite", "gw_final")
MB = 1024 * 1024


class OwnerStatus:
    def __init__(
        self,
        *,
        clock: Clock,
        started_at: datetime,
        version: str,
        completions: CompletionStore,
        usage: DatabaseUsage,
    ) -> None:
        self._clock = clock
        self._started_at = started_at
        self._version = version
        self._completions = completions
        self._usage = usage

    async def report(self) -> str:
        uptime = _duration(self._clock.now() - self._started_at)
        lines = [
            texts.STATUS_TITLE,
            texts.status_uptime(uptime, self._version),
            texts.STATUS_COMPLETIONS,
        ]
        try:
            latest = await self._completions.latest(STATUS_JOBS)
            size = await self._usage.size_bytes()
        except Exception as error:  # the database is down: say so instead of failing
            log.warning("status: database unreachable: %s", type(error).__name__)
            lines.extend(texts.status_completion_unknown(job) for job in STATUS_JOBS)
            lines.append(texts.NEON_UNREACHABLE)
        else:
            for job in STATUS_JOBS:
                done = latest.get(job)
                period, at = (done.period, done.completed_at) if done else (None, None)
                lines.append(texts.status_completion(job, period, at))
            lines.append(texts.NEON_REACHABLE)
            lines.append(texts.database_size(*storage_share(size, self._usage.storage_limit_bytes)))
        lines.append(texts.COMPUTE_HOURS_UNREADABLE)
        return "\n".join(lines)


def storage_share(size: int, limit: int) -> tuple[float, int, int]:
    """(size in MB, limit in MB, whole percent used)."""
    return size / MB, limit // MB, size * 100 // limit


def _duration(elapsed: timedelta) -> str:
    minutes = int(elapsed.total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    return texts.duration(days, hours, minutes)
