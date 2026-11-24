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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, ClassVar, Literal, Protocol

from fplbot.clock import Clock
from fplbot.sources.limiter import Priority, RateLimiter

__all__ = [
    "FplBadData",
    "FplBlocked",
    "FplClub",
    "FplDown",
    "FplEntry",
    "FplError",
    "FplFixture",
    "FplFootballer",
    "FplGameweek",
    "FplH2hMatch",
    "FplHistory",
    "FplHistoryGameweek",
    "FplLeague",
    "FplLiveFootballer",
    "FplPick",
    "FplPicks",
    "FplReference",
    "FplResponse",
    "FplSource",
    "FplStanding",
    "FplStandings",
    "FplTransport",
    "FplUnexpectedStatus",
    "FplUpdating",
    "LeagueKind",
    "Lookup",
    "PoliteFplClient",
    "Position",
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

    async def reference(self, max_age: timedelta = BOOTSTRAP_MAX_AGE) -> FplReference:
        """Gameweeks, clubs and Footballers from the in-memory ``bootstrap-static``."""
        data = await self.bootstrap_static(max_age)
        return _parsed(_reference, data)

    async def fixtures(self) -> tuple[FplFixture, ...]:
        """Every fixture of the season (``fixtures/``)."""
        data = await self.get_json("fixtures/")
        if data is None:
            raise FplUnexpectedStatus(404)
        return _parsed(_fixtures, data)

    async def history(self, entry_id: int) -> FplHistory | None:
        """A team's season so far (``entry/{id}/history/``); ``None`` if there is no such team."""
        data = await self.get_json(f"entry/{entry_id}/history/")
        return None if data is None else _parsed(_history, data)

    async def picks(self, entry_id: int, gameweek: int) -> FplPicks | None:
        """A team's Squad for a Gameweek whose deadline has passed. ``None`` when FPL hides or
        has no picks for it (404: the upcoming Gameweek, or before the team existed)."""
        data = await self.get_json(f"entry/{entry_id}/event/{gameweek}/picks/")
        return None if data is None else _parsed(lambda d: _picks(gameweek, d), data)

    async def live(self, gameweek: int) -> tuple[FplLiveFootballer, ...] | None:
        """Every Footballer's stats in a Gameweek (``event/{gw}/live/``); ``None`` on 404."""
        data = await self.get_json(f"event/{gameweek}/live/")
        return None if data is None else _parsed(_live, data)

    async def team(self, entry_id: int) -> FplEntry | None:
        """An FPL team for jobs: ``None`` if there is no such team, ``FplError`` if FPL fails."""
        data = await self.get_json(f"entry/{entry_id}/")
        return None if data is None else _parsed(_entry, data)

    async def standings(
        self, kind: LeagueKind, league_id: int, page: int = 1
    ) -> FplStandings | None:
        """One page (50 rows) of a Mini-league's table; ``None`` if FPL has no such league."""
        path = f"leagues-{kind}/{league_id}/standings/"
        if page > 1:
            path += f"?page_standings={page}"
        data = await self.get_json(path)
        return None if data is None else _parsed(lambda d: _standings(page, d), data)

    async def h2h_matches(
        self, league_id: int, gameweek: int, entry_id: int
    ) -> tuple[FplH2hMatch, ...] | None:
        """A head-to-head league's matches of ``entry_id`` in ``gameweek``; ``None`` on 404."""
        path = f"leagues-h2h-matches/league/{league_id}/?event={gameweek}&entry={entry_id}&page=1"
        data = await self.get_json(path)
        return None if data is None else _parsed(_h2h_matches, data)

    async def entry(self, entry_id: int) -> FplEntry | Lookup:
        """An FPL team. Fail-soft for interactive callers: FPL failing is
        ``Lookup.UNAVAILABLE`` rather than an ``FplError``."""
        try:
            data = await self.get_json(f"entry/{entry_id}/")
        except FplError:
            return Lookup.UNAVAILABLE
        if data is None:
            return Lookup.NOT_FOUND
        try:
            return _entry(data)
        except ValueError, KeyError, TypeError, AttributeError:
            return Lookup.UNAVAILABLE


class Lookup(Enum):
    """Why a lookup returned no data."""

    NOT_FOUND = "not_found"  # FPL answered 404: no such entry
    UNAVAILABLE = "unavailable"  # FPL could not be reached or answered something unusable


type LeagueKind = Literal["classic", "h2h"]


@dataclass(frozen=True)
class FplLeague:
    id: int
    kind: LeagueKind
    name: str
    # The team's rank in the league, as ``entry/{id}/`` reports it (None if absent).
    entry_rank: int | None = None


@dataclass(frozen=True)
class FplEntry:
    """An FPL team (``entry/{id}/``). The manager's name is for the "Is that you?" check only:
    never store it."""

    id: int
    team_name: str
    manager_first_name: str
    manager_last_name: str
    overall_rank: int | None
    # Private classic and head-to-head leagues (Mini-leagues), in FPL's order.
    mini_leagues: tuple[FplLeague, ...]


# FPL's league_type: "x" is a private league; "s" a system one (Overall, countries, clubs...).
_PRIVATE = "x"


def _entry(data: dict[str, Any]) -> FplEntry:
    leagues: dict[str, list[dict[str, Any]]] = data.get("leagues") or {}
    mini_leagues = tuple(
        FplLeague(
            int(league["id"]), kind, str(league["name"]), _optional_int(league.get("entry_rank"))
        )
        for kind in ("classic", "h2h")
        for league in leagues.get(kind) or []
        if league.get("league_type") == _PRIVATE
    )
    rank = data.get("summary_overall_rank")
    return FplEntry(
        id=int(data["id"]),
        team_name=str(data["name"]),
        manager_first_name=str(data.get("player_first_name") or ""),
        manager_last_name=str(data.get("player_last_name") or ""),
        overall_rank=int(rank) if rank else None,
        mini_leagues=mini_leagues,
    )


# --- Reference data, history and picks -----------------------------------------------------

type Position = Literal["GKP", "DEF", "MID", "FWD"]
_POSITIONS: dict[int, Position] = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


@dataclass(frozen=True)
class FplGameweek:
    id: int
    deadline: datetime
    finished: bool
    data_checked: bool


@dataclass(frozen=True)
class FplClub:
    id: int
    name: str
    short_name: str


@dataclass(frozen=True)
class FplFootballer:
    id: int
    web_name: str
    first_name: str
    second_name: str
    club_id: int
    position: Position
    now_cost: int  # tenths of a million: 55 is £5.5m


@dataclass(frozen=True)
class FplReference:
    """The slow-changing part of ``bootstrap-static``."""

    gameweeks: tuple[FplGameweek, ...]
    clubs: tuple[FplClub, ...]
    footballers: tuple[FplFootballer, ...]


@dataclass(frozen=True)
class FplFixture:
    id: int
    gameweek: int | None  # None while unscheduled (postponed)
    kickoff: datetime | None
    home_club_id: int
    away_club_id: int
    home_difficulty: int | None
    away_difficulty: int | None
    home_score: int | None
    away_score: int | None
    finished: bool


@dataclass(frozen=True)
class FplHistoryGameweek:
    """One Gameweek of a team's season. Money is in tenths of a million."""

    gameweek: int
    points: int
    total_points: int
    rank: int | None
    overall_rank: int | None
    bank: int
    value: int
    transfers: int
    transfers_cost: int
    points_on_bench: int
    chip: str | None  # e.g. "wildcard", "bboost", "3xc", "freehit"


@dataclass(frozen=True)
class FplHistory:
    gameweeks: tuple[FplHistoryGameweek, ...]


@dataclass(frozen=True)
class FplPick:
    footballer_id: int
    slot: int  # 1-11 the XI in formation order, 12-15 the bench in order
    multiplier: int
    is_captain: bool
    is_vice_captain: bool


@dataclass(frozen=True)
class FplPicks:
    gameweek: int
    active_chip: str | None
    picks: tuple[FplPick, ...]


def _parsed[T](parse: Callable[[Any], T], data: Any) -> T:
    try:
        return parse(data)
    except ValueError, KeyError, TypeError, AttributeError:
        raise FplBadData(200) from None


def _when(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _reference(data: dict[str, Any]) -> FplReference:
    return FplReference(
        gameweeks=tuple(
            FplGameweek(
                id=int(event["id"]),
                deadline=_when(event["deadline_time"]),
                finished=bool(event.get("finished")),
                data_checked=bool(event.get("data_checked")),
            )
            for event in data["events"]
        ),
        clubs=tuple(
            FplClub(int(team["id"]), str(team["name"]), str(team["short_name"]))
            for team in data["teams"]
        ),
        footballers=tuple(
            FplFootballer(
                id=int(element["id"]),
                web_name=str(element["web_name"]),
                first_name=str(element.get("first_name") or ""),
                second_name=str(element.get("second_name") or ""),
                club_id=int(element["team"]),
                position=_POSITIONS[int(element["element_type"])],
                now_cost=int(element["now_cost"]),
            )
            for element in data["elements"]
        ),
    )


def _fixtures(data: list[dict[str, Any]]) -> tuple[FplFixture, ...]:
    return tuple(
        FplFixture(
            id=int(fixture["id"]),
            gameweek=_optional_int(fixture.get("event")),
            kickoff=_when(fixture["kickoff_time"]) if fixture.get("kickoff_time") else None,
            home_club_id=int(fixture["team_h"]),
            away_club_id=int(fixture["team_a"]),
            home_difficulty=_optional_int(fixture.get("team_h_difficulty")),
            away_difficulty=_optional_int(fixture.get("team_a_difficulty")),
            home_score=_optional_int(fixture.get("team_h_score")),
            away_score=_optional_int(fixture.get("team_a_score")),
            finished=bool(fixture.get("finished")),
        )
        for fixture in data
    )


def _history(data: dict[str, Any]) -> FplHistory:
    played: list[dict[str, Any]] = data.get("chips") or []
    chips = {int(chip["event"]): str(chip["name"]) for chip in played}
    return FplHistory(
        tuple(
            FplHistoryGameweek(
                gameweek=int(row["event"]),
                points=int(row["points"]),
                total_points=int(row["total_points"]),
                rank=_optional_int(row.get("rank")),
                overall_rank=_optional_int(row.get("overall_rank")),
                bank=int(row["bank"]),
                value=int(row["value"]),
                transfers=int(row["event_transfers"]),
                transfers_cost=int(row["event_transfers_cost"]),
                points_on_bench=int(row["points_on_bench"]),
                chip=chips.get(int(row["event"])),
            )
            for row in data["current"]
        )
    )


def _picks(gameweek: int, data: dict[str, Any]) -> FplPicks:
    chip = data.get("active_chip")
    return FplPicks(
        gameweek=gameweek,
        active_chip=str(chip) if chip else None,
        picks=tuple(
            FplPick(
                footballer_id=int(pick["element"]),
                slot=int(pick["position"]),
                multiplier=int(pick["multiplier"]),
                is_captain=bool(pick["is_captain"]),
                is_vice_captain=bool(pick["is_vice_captain"]),
            )
            for pick in data["picks"]
        ),
    )


# --- Mini-league standings and head-to-head matches (ticket 32) ----------------------------

STANDINGS_PAGE_SIZE = 50


@dataclass(frozen=True)
class FplStanding:
    """One row of a league table. ``points`` is the table's ranking figure: total FPL points in
    a classic league, league points (3 a win) in a head-to-head one. The manager's own name is
    never read: only the team's."""

    position: int  # 1-based place in FPL's order (rank_sort), unique even when ranks tie
    entry_id: int
    team_name: str
    rank: int
    last_rank: int | None  # None for a team new to the table
    points: int


@dataclass(frozen=True)
class FplStandings:
    league_name: str
    page: int
    has_next: bool
    rows: tuple[FplStanding, ...]


@dataclass(frozen=True)
class FplH2hMatch:
    entry_1: int | None  # None: a bye (FPL's "average" opponent)
    entry_1_name: str
    entry_2: int | None
    entry_2_name: str


def _standings(page: int, data: dict[str, Any]) -> FplStandings:
    table: dict[str, Any] = data["standings"]
    results: list[dict[str, Any]] = table["results"]
    first = (page - 1) * STANDINGS_PAGE_SIZE
    return FplStandings(
        league_name=str(data["league"]["name"]),
        page=page,
        has_next=bool(table.get("has_next")),
        rows=tuple(
            FplStanding(
                position=first + index + 1,
                entry_id=int(row["entry"]),
                team_name=str(row["entry_name"]),
                rank=int(row["rank"]),
                last_rank=int(row["last_rank"]) if row.get("last_rank") else None,
                points=int(row["total"]),
            )
            for index, row in enumerate(results)
        ),
    )


def _h2h_matches(data: dict[str, Any]) -> tuple[FplH2hMatch, ...]:
    results: list[dict[str, Any]] = data["results"]
    return tuple(
        FplH2hMatch(
            entry_1=_optional_int(match.get("entry_1_entry")),
            entry_1_name=str(match.get("entry_1_name") or ""),
            entry_2=_optional_int(match.get("entry_2_entry")),
            entry_2_name=str(match.get("entry_2_name") or ""),
        )
        for match in results
    )


# --- Per-Gameweek Footballer stats (ticket 33) ----------------------------------------------


@dataclass(frozen=True)
class FplLiveFootballer:
    """A Footballer's totals over a Gameweek's fixtures (``event/{gw}/live/``). Expected
    figures are FPL's decimal strings parsed to floats; fields FPL leaves out are ``None``."""

    footballer_id: int
    total_points: int
    minutes: int
    starts: int | None
    goals_scored: int | None
    assists: int | None
    clean_sheets: int | None
    goals_conceded: int | None
    saves: int | None
    bonus: int | None
    bps: int | None
    expected_goals: float | None
    expected_assists: float | None
    expected_goals_conceded: float | None


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _live(data: dict[str, Any]) -> tuple[FplLiveFootballer, ...]:
    elements: list[dict[str, Any]] = data["elements"]
    footballers: list[FplLiveFootballer] = []
    for element in elements:
        stats: dict[str, Any] = element["stats"]
        footballers.append(
            FplLiveFootballer(
                footballer_id=int(element["id"]),
                total_points=int(stats["total_points"]),
                minutes=int(stats["minutes"]),
                starts=_optional_int(stats.get("starts")),
                goals_scored=_optional_int(stats.get("goals_scored")),
                assists=_optional_int(stats.get("assists")),
                clean_sheets=_optional_int(stats.get("clean_sheets")),
                goals_conceded=_optional_int(stats.get("goals_conceded")),
                saves=_optional_int(stats.get("saves")),
                bonus=_optional_int(stats.get("bonus")),
                bps=_optional_int(stats.get("bps")),
                expected_goals=_optional_float(stats.get("expected_goals")),
                expected_assists=_optional_float(stats.get("expected_assists")),
                expected_goals_conceded=_optional_float(stats.get("expected_goals_conceded")),
            )
        )
    return tuple(footballers)
