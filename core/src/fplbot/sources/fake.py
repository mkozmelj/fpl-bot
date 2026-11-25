"""A fake FPL transport serving recorded fixtures, for tests and for running with zero keys.

Fixture layout mirrors the API path: ``bootstrap-static/`` is served from
``<fixtures_dir>/bootstrap-static.json`` and ``entry/1001/event/11/picks/`` from
``<fixtures_dir>/entry/1001/event/11/picks.json``. A path with no fixture answers 404.

Awkward cases (403, 429, 503 "updating", a sequence of answers) are scripted per test with
``respond``. Fixtures must be small and synthetic: never commit real FPL data.
"""

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fplbot.clock import Clock, SystemClock
from fplbot.sources.fpl import FplResponse

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "fpl"


@dataclass(frozen=True)
class FplRequest:
    """One request as it reached the transport: when, which path, which headers."""

    at: datetime
    path: str
    headers: Mapping[str, str]


class FakeFplTransport:
    def __init__(self, fixtures_dir: Path = DEFAULT_FIXTURES_DIR, clock: Clock | None = None):
        self._fixtures_dir = fixtures_dir
        self._clock: Clock = clock or SystemClock()
        self._scripted: dict[str, deque[FplResponse]] = {}
        self.requests: list[FplRequest] = []

    @property
    def requested_paths(self) -> list[str]:
        return [request.path for request in self.requests]

    def respond(self, path: str, *responses: FplResponse) -> None:
        """Answer ``path`` with these responses in order; the last one repeats."""
        self._scripted[_normalise(path)] = deque(responses)

    async def get(self, path: str, headers: Mapping[str, str]) -> FplResponse:
        key = _normalise(path)
        self.requests.append(FplRequest(self._clock.now(), key, dict(headers)))
        scripted = self._scripted.get(key)
        if scripted:
            return scripted.popleft() if len(scripted) > 1 else scripted[0]
        fixture = self._fixtures_dir / f"{key}.json"
        if fixture.is_file():
            return FplResponse(200, fixture.read_bytes(), {"content-type": "application/json"})
        return FplResponse(404, b'{"detail":"Not found."}')


def _normalise(path: str) -> str:
    return path.strip("/")
