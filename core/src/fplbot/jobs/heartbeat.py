"""The liveness heartbeat (ticket 23): a ping to ``HEARTBEAT_URL`` every 5 minutes.

The owner's own monitoring service expects the pings and alerts when they stop; Railway's health
checks are HTTP-only and the bot serves no HTTP. A ping goes out only while the event loop runs
this task and the scheduler is alive, so a crashed scheduler (or a blocked loop) stops the pings.
The ping is a bare GET: it never touches the database (Neon can stay asleep) and carries no
Member data. No URL configured, no task. A failed ping is logged (type only: the URL is a
secret) and the next one is tried 5 minutes later.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

import httpx

from fplbot.clock import Clock

log = logging.getLogger(__name__)

HEARTBEAT_EVERY = timedelta(minutes=5)
PING_TIMEOUT_SECONDS = 10.0


class Pinger(Protocol):
    async def ping(self, url: str) -> None:
        """Send one ping to ``url``; raise if it did not get through."""
        ...


class HttpxPinger:
    """The production pinger: one GET with a short timeout."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=PING_TIMEOUT_SECONDS)

    async def ping(self, url: str) -> None:
        response = await self._client.get(url)
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()


class Heartbeat:
    def __init__(
        self, url: str | None, pinger: Pinger | None, clock: Clock, healthy: Callable[[], bool]
    ) -> None:
        self._url = url
        self._pinger = pinger
        self._clock = clock
        self._healthy = healthy
        self._task: asyncio.Task[None] | None = None

    @property
    def tasks(self) -> set[asyncio.Task[None]]:
        """The heartbeat's task while it runs (the test harness settles it)."""
        return {self._task} if self._task is not None and not self._task.done() else set()

    def start(self) -> None:
        if self._url is None or self._pinger is None or self.tasks:
            return
        self._task = asyncio.create_task(self._run(self._url, self._pinger), name="heartbeat")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self, url: str, pinger: Pinger) -> None:
        while True:
            if self._healthy():
                try:
                    await pinger.ping(url)
                except Exception as error:
                    log.warning("heartbeat ping failed: %s", type(error).__name__)
            else:
                log.warning("heartbeat skipped: the scheduler is not running")
            await self._clock.sleep(HEARTBEAT_EVERY.total_seconds())
