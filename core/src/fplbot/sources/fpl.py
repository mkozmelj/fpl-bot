"""The FPL API adapter.

Two layers:

- ``FplTransport`` is the raw "GET a path, get a status and bytes" boundary. The live transport
  (ticket 27) talks HTTP to FPL; ``FakeFplTransport`` serves recorded fixtures. Politeness (the
  shared 1 req/s limiter, retries, User-Agent, conditional requests) sits *above* the transport,
  so it is exercised in tests too.
- ``FplSource`` turns responses into data for the rest of the bot and is fail-soft: an
  unavailable endpoint gives ``None`` rather than an exception.

Raw responses are never stored; callers keep only what they need.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class FplResponse:
    status: int
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict[str, str])

    @property
    def ok(self) -> bool:
        return self.status == 200

    def json(self) -> Any:
        return json.loads(self.body)


class FplTransport(Protocol):
    async def get(self, path: str) -> FplResponse:
        """GET ``https://fantasy.premierleague.com/api/<path>``, e.g. ``bootstrap-static/``."""
        ...


class Lookup(Enum):
    """Why a lookup returned no data."""

    NOT_FOUND = "not_found"  # FPL answered 404: no such entry
    UNAVAILABLE = "unavailable"  # FPL could not be reached or answered something unusable


@dataclass(frozen=True)
class FplLeague:
    id: int
    kind: Literal["classic", "h2h"]
    name: str


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


class FplSource:
    def __init__(self, transport: FplTransport) -> None:
        self._transport = transport

    async def bootstrap_static(self) -> dict[str, Any] | None:
        response = await self._transport.get("bootstrap-static/")
        if not response.ok:
            return None
        data: dict[str, Any] = response.json()
        return data

    async def entry(self, entry_id: int) -> FplEntry | Lookup:
        response = await self._transport.get(f"entry/{entry_id}/")
        if response.status == 404:
            return Lookup.NOT_FOUND
        if not response.ok:
            return Lookup.UNAVAILABLE
        try:
            return _entry(response.json())
        except ValueError, KeyError, TypeError:
            return Lookup.UNAVAILABLE


# FPL's league_type: "x" is a private league; "s" a system one (Overall, countries, clubs...).
_PRIVATE = "x"


def _entry(data: dict[str, Any]) -> FplEntry:
    leagues: dict[str, list[dict[str, Any]]] = data.get("leagues") or {}
    mini_leagues = tuple(
        FplLeague(int(league["id"]), kind, str(league["name"]))
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
