"""The one shared rate limiter for all FPL traffic: at most one request start per interval.

Waiting requests are served by priority (lower value first), then in arrival order. Every wait is
a ``Clock.sleep``, never a bare event, so a fake clock can run the limiter in simulated time.
"""

import asyncio
import heapq
from datetime import datetime, timedelta
from enum import IntEnum
from itertools import count

from fplbot.clock import Clock

# How long a waiter that is not first in line naps when a slot is free but the first in line
# has not woken up yet. Only matters for a few milliseconds around each slot.
_NOT_YOUR_TURN_NAP = 0.05


class Priority(IntEnum):
    """Who goes first when several FPL requests are waiting. Lower goes first."""

    INTERACTIVE = 0  # a Member or the owner is waiting for a reply
    PRICE_ALERT = 1
    ROUTINE = 2  # post-deadline picks, GW-final refreshes, price archives
    ELITE = 3  # the Elite sampler: thousands of requests, nobody waiting on any single one


class RateLimiter:
    def __init__(self, clock: Clock, interval: timedelta) -> None:
        self._clock = clock
        self._interval = interval
        self._next_free: datetime | None = None
        self._queue: list[tuple[int, int]] = []
        self._arrivals = count()

    async def acquire(self, priority: Priority) -> None:
        """Wait for this request's turn; return when it may start."""
        ticket = (int(priority), next(self._arrivals))
        heapq.heappush(self._queue, ticket)
        try:
            while True:
                now, next_free = self._clock.now(), self._next_free
                if next_free is not None and now < next_free:
                    await self._clock.sleep((next_free - now).total_seconds())
                elif self._queue[0] == ticket:
                    heapq.heappop(self._queue)
                    self._next_free = now + self._interval
                    return
                else:
                    await self._clock.sleep(_NOT_YOUR_TURN_NAP)
        except asyncio.CancelledError:
            if ticket in self._queue:
                self._queue.remove(ticket)
                heapq.heapify(self._queue)
            raise
