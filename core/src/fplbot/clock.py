"""The one source of "now". Inject a Clock everywhere time matters so tests can use a fake one.

Waiting goes through the clock too (``sleep``), so a fake clock can run rate limits, backoff and
scheduled waits in simulated time.
"""

import asyncio
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """The current moment as a timezone-aware UTC datetime."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Wait ``seconds`` of this clock's time."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(seconds, 0))
