"""The live FPL transport over httpx. Politeness lives above it in ``PoliteFplClient``."""

from collections.abc import Mapping

import httpx

from fplbot.sources.fpl import FplResponse

FPL_API = "https://fantasy.premierleague.com/api/"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class HttpxFplTransport:
    def __init__(self, base_url: str = FPL_API) -> None:
        # No default headers of our own and no cookies: every header comes from the caller.
        self._client = httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT, follow_redirects=False)

    async def get(self, path: str, headers: Mapping[str, str]) -> FplResponse:
        try:
            response = await self._client.get(path.lstrip("/"), headers=dict(headers))
        except httpx.TransportError:
            return FplResponse(0)
        self._client.cookies.clear()
        return FplResponse(
            response.status_code,
            response.content,
            {key.lower(): value for key, value in response.headers.items()},
        )

    async def aclose(self) -> None:
        await self._client.aclose()
