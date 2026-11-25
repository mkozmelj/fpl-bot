"""Daily Neon storage check (ticket 23 cost guard): one owner DM when the database passes 70% of
the plan's storage (``DATABASE_STORAGE_LIMIT_MB``, Neon Free: 1 GB).

The DM is sent once (an owner notice in the database, so restarts don't repeat it); once the
database is back under 70% the notice is cleared and a later rise is reported again. The
"compute hours past 80%" DM is skipped: compute usage is readable only through the Neon API,
which needs a key (store/usage.py); the runbook has a monthly console check instead.
"""

import logging
from datetime import time

from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.owner_alerts import SendToOwner
from fplbot.delivery.status import storage_share
from fplbot.sources.fpl import FplSource
from fplbot.store.owner_notices import OwnerNotices
from fplbot.store.usage import DatabaseUsage

log = logging.getLogger(__name__)

STORAGE_CHECK_JOB = "storage-check"
STORAGE_CHECK_AT = time(4, 30)  # after the 04:00 Member backup
WARN_AT_PERCENT = 70
NOTICE = "neon-storage-70"


class StorageCheck:
    def __init__(
        self, usage: DatabaseUsage, notices: OwnerNotices, send: SendToOwner, clock: Clock
    ) -> None:
        self._usage = usage
        self._notices = notices
        self._send = send
        self._clock = clock

    async def run(self, fpl: FplSource) -> None:
        """The job (no FPL requests)."""
        size_mb, limit_mb, percent = storage_share(
            await self._usage.size_bytes(), self._usage.storage_limit_bytes
        )
        if percent < WARN_AT_PERCENT:
            await self._notices.clear(NOTICE)
            return
        if await self._notices.claim(NOTICE, self._clock.now()):
            log.info("owner told: database storage at %d%%", percent)
            await self._send(texts.storage_warning(size_mb, limit_mb, percent))
