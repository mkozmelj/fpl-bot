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
from typing import Any, Protocol


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


class FplSource:
    def __init__(self, transport: FplTransport) -> None:
        self._transport = transport

    async def bootstrap_static(self) -> dict[str, Any] | None:
        response = await self._transport.get("bootstrap-static/")
        if not response.ok:
            return None
        data: dict[str, Any] = response.json()
        return data
