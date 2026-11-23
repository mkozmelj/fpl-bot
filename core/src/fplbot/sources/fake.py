"""A fake FPL transport serving recorded fixtures, for tests and for running with zero keys.

Fixture layout mirrors the API path: ``bootstrap-static/`` is served from
``<fixtures_dir>/bootstrap-static.json`` and ``entry/1001/event/11/picks/`` from
``<fixtures_dir>/entry/1001/event/11/picks.json``. A path with no fixture answers 404.

Awkward cases (403, 429, 503 "updating", a sequence of answers) are scripted per test with
``respond``. Fixtures must be small and synthetic: never commit real FPL data.
"""

from collections import deque
from pathlib import Path

from fplbot.sources.fpl import FplResponse

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "fpl"


class FakeFplTransport:
    def __init__(self, fixtures_dir: Path = DEFAULT_FIXTURES_DIR) -> None:
        self._fixtures_dir = fixtures_dir
        self._scripted: dict[str, deque[FplResponse]] = {}
        self.requested_paths: list[str] = []

    def respond(self, path: str, *responses: FplResponse) -> None:
        """Answer ``path`` with these responses in order; the last one repeats."""
        self._scripted[_normalise(path)] = deque(responses)

    async def get(self, path: str) -> FplResponse:
        key = _normalise(path)
        self.requested_paths.append(key)
        scripted = self._scripted.get(key)
        if scripted:
            return scripted.popleft() if len(scripted) > 1 else scripted[0]
        fixture = self._fixtures_dir / f"{key}.json"
        if fixture.is_file():
            return FplResponse(200, fixture.read_bytes(), {"content-type": "application/json"})
        return FplResponse(404, b'{"detail":"Not found."}')


def _normalise(path: str) -> str:
    return path.strip("/")
