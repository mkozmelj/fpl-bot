"""The FPL API adapter.

Three layers, top to bottom:

- ``FplSource`` turns responses into data for the rest of the bot. A missing resource (404) is
  ``None``; FPL being unavailable is an ``FplError`` whose ``code`` is a short fixed string the
  job runner reports to the owner. ``bootstrap-static`` is held in memory only.
- ``PoliteFplClient`` is the one way to reach FPL: one shared rate limiter (1 request a second,
  by ``Priority``), one generic browser User-Agent, conditional requests, backoff with jitter on
  429/5xx honouring Retry-After (at most 5 tries), and no retry on 403 or "being updated".
- ``FplTransport`` is the raw "GET a path with these headers" boundary: ``HttpxFplTransport``
  (live) or ``FakeFplTransport`` (recorded fixtures). Everything above it runs in tests too.

Raw responses are never stored in the database; callers keep only what they need.
"""

import asyncio
import email.utils
import json
import logging
import random
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Protocol

from fplbot.clock import Clock
from fplbot.sources.limiter import Priority, RateLimiter

__all__ = [
    "FplBadData",
    "FplBlocked",
    "FplDown",
    "FplError",
    "FplResponse",
    "FplSource",
    "FplTransport",
    "FplUnexpectedStatus",
    "FplUpdating",
    "PoliteFplClient",
    "Priority",
]

log = logging.getLogger(__name__)

# The same generic browser string the Railway probe used: no personal details, URL or repo name.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
REQUEST_HEADERS: Mapping[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
}

REQUEST_INTERVAL = timedelta(seconds=1)
MAX_TRIES = 5
# Backoff before try n+1 is BACKOFF_BASE * 2**(n-1), jittered by +/-25%: about 2, 4, 8, 16 s.
BACKOFF_BASE = 2.0
BACKOFF_JITTER = 0.25
# A Retry-After longer than this is not waited out inside a job: the try counts as given up.
MAX_RETRY_AFTER = 300.0
BOOTSTRAP_MAX_AGE = timedelta(minutes=15)
# Bodies kept in memory only so a 304 answer can be served; bounded so sampling stays small.
CONDITIONAL_CACHE_SIZE = 256


@dataclass(frozen=True)
class FplResponse:
    status: int  # 0: no answer at all (timeout, connection error)
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict[str, str])

    @property
    def ok(self) -> bool:
        return self.status == 200

    def json(self) -> Any:
        return json.loads(self.body)

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        return next((v for k, v in self.headers.items() if k.lower() == wanted), None)


class FplTransport(Protocol):
    async def get(self, path: str, headers: Mapping[str, str]) -> FplResponse:
        """GET ``https://fantasy.premierleague.com/api/<path>`` (e.g. ``bootstrap-static/``),
        sending exactly ``headers``. Network failures answer status 0, never raise."""
        ...


class FplError(Exception):
    """FPL could not give us the data. ``code`` is the fixed code the owner is told."""

    code: ClassVar[str] = "FPL-ERROR"

    def __init__(self, status: int | None = None) -> None:
        # Never the path: paths carry team and league IDs.
        super().__init__(f"{self.code} (status {status})" if status is not None else self.code)
        self.status = status


class FplBlocked(FplError):
    """403: FPL refused us. Never retried; the job pauses until its next run."""

    code = "FPL-403"


class FplUpdating(FplError):
    """FPL answered "The game is being updated." Not retried here; callers decide to wait."""

    code = "FPL-UPDATING"


class FplDown(FplError):
    """429, 5xx or no answer, still failing after ``MAX_TRIES`` tries."""

    code = "FPL-DOWN"


class FplUnexpectedStatus(FplError):
    """An answer that is none of the above (e.g. 400, 401)."""

    code = "FPL-HTTP"


class FplBadData(FplError):
    """A 200 whose body is not the JSON we need (HTML, or required fields missing)."""

    code = "FPL-BAD-DATA"


class PoliteFplClient:
    def __init__(self, transport: FplTransport, clock: Clock) -> None:
        self._transport = transport
        self._clock = clock
        self._limiter = RateLimiter(clock, REQUEST_INTERVAL)
        self._jitter = random.Random()  # noqa: S311 - backoff jitter, not security
        self._conditional: OrderedDict[str, FplResponse] = OrderedDict()

    @property
    def clock(self) -> Clock:
        return self._clock

    async def get(self, path: str, priority: Priority) -> FplResponse | None:
        """The 200 answer for ``path``, ``None`` on 404, else an ``FplError``."""
        attempt = 0
        while True:
            attempt += 1
            await self._limiter.acquire(priority)
            response = await self._transport.get(path, self._headers_for(path))
            if response.status == 304 and (cached := self._conditional.get(path)):
                self._conditional.move_to_end(path)
                return cached
            if response.ok:
                self._remember(path, response)
                return response
            if response.status == 404:
                return None
            if _is_updating(response):
                raise FplUpdating(response.status)
            if response.status == 403:
                raise FplBlocked(403)
            if not _is_retryable(response.status):
                raise FplUnexpectedStatus(response.status)
            delay = self._retry_delay(response, attempt) if attempt < MAX_TRIES else None
            if delay is None:
                raise FplDown(response.status)
            log.info("fpl status %d, retrying in %.1fs", response.status, delay)
            await self._clock.sleep(delay)

    def _headers_for(self, path: str) -> dict[str, str]:
        headers = dict(REQUEST_HEADERS)
        if cached := self._conditional.get(path):
            if etag := cached.header("ETag"):
                headers["If-None-Match"] = etag
            if last_modified := cached.header("Last-Modified"):
                headers["If-Modified-Since"] = last_modified
        return headers

    def _remember(self, path: str, response: FplResponse) -> None:
        if response.header("ETag") is None and response.header("Last-Modified") is None:
            self._conditional.pop(path, None)
            return
        self._conditional[path] = response
        self._conditional.move_to_end(path)
        while len(self._conditional) > CONDITIONAL_CACHE_SIZE:
            self._conditional.popitem(last=False)

    def _retry_delay(self, response: FplResponse, attempt: int) -> float | None:
        retry_after = _retry_after_seconds(response, self._clock.now())
        if retry_after is not None:
            return retry_after if retry_after <= MAX_RETRY_AFTER else None
        backoff = BACKOFF_BASE * 2 ** (attempt - 1)
        return backoff * self._jitter.uniform(1 - BACKOFF_JITTER, 1 + BACKOFF_JITTER)


def _is_retryable(status: int) -> bool:
    return status in (0, 429) or status >= 500


def _is_updating(response: FplResponse) -> bool:
    return b"being updated" in response.body.lower()


def _retry_after_seconds(response: FplResponse, now: datetime) -> float | None:
    value = response.header("Retry-After")
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - now).total_seconds(), 0.0)


@dataclass
class _Bootstrap:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    data: dict[str, Any] | None = None
    fetched_at: datetime | None = None


_BOOTSTRAP_REQUIRED = ("events", "teams", "elements", "element_types")


class FplSource:
    """FPL data for one kind of caller. ``with_priority`` gives a view for another kind; all
    views share the client (and so the rate limit) and the in-memory ``bootstrap-static``."""

    def __init__(
        self,
        client: PoliteFplClient,
        priority: Priority = Priority.ROUTINE,
        *,
        _bootstrap: _Bootstrap | None = None,
    ) -> None:
        self._client = client
        self._priority = priority
        self._bootstrap = _bootstrap or _Bootstrap()

    def with_priority(self, priority: Priority) -> FplSource:
        return FplSource(self._client, priority, _bootstrap=self._bootstrap)

    async def get_json(self, path: str) -> Any | None:
        """Decoded JSON for ``path``; ``None`` when FPL has no such resource (404)."""
        response = await self._client.get(path, self._priority)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError:
            raise FplBadData(response.status) from None

    async def bootstrap_static(self, max_age: timedelta = BOOTSTRAP_MAX_AGE) -> dict[str, Any]:
        """``bootstrap-static``, refetched when the copy in memory is older than ``max_age``
        (pass ``timedelta(0)`` to force a fetch). Held in memory only, never stored."""
        cache = self._bootstrap
        async with cache.lock:
            now = self._client.clock.now()
            if cache.data is not None and cache.fetched_at and now - cache.fetched_at < max_age:
                return cache.data
            data = await self.get_json("bootstrap-static/")
            if not isinstance(data, dict) or any(
                not isinstance(data.get(key), list)  # pyright: ignore[reportUnknownMemberType]
                for key in _BOOTSTRAP_REQUIRED
            ):
                raise FplBadData(200)
            bootstrap: dict[str, Any] = data  # pyright: ignore[reportUnknownVariableType]
            cache.data, cache.fetched_at = bootstrap, now
            return bootstrap
