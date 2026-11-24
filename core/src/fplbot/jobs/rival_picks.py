"""Fetching Rival picks (ticket 33) for the Rival gap.

The Rivals are the teams of every stored Followed-league table plus the Members' head-to-head
opponents, minus the Members' own teams (``RivalPicksStore.rival_entries``). For a Gameweek whose
deadline has passed, ``fetch_missing`` reads the picks of each Rival that has none stored for it
yet. The post-deadline job calls it after the Members' picks; the Followed-league recompute
calls it for the last deadline's Gameweek, so Rivals of a Member who joins (or switches Goal)
between deadlines have last-deadline picks too. With nothing missing it makes no request.
"""

import asyncio
import logging

from fplbot.sources.fpl import FplSource
from fplbot.store.rivals import RivalPicksStore

log = logging.getLogger(__name__)


class RivalPicks:
    def __init__(self, store: RivalPicksStore) -> None:
        self._store = store
        # The post-deadline job and a recompute may run at once: each Rival is read once.
        self._lock = asyncio.Lock()

    async def fetch_missing(self, fpl: FplSource, season: str, gameweek: int) -> None:
        """Store each Rival's Squad at ``gameweek``'s deadline unless stored. Raises
        ``FplError``; picks read before a failure stay stored."""
        async with self._lock:
            entries = await self._store.rival_entries(season)
            missing = await self._store.missing(season, gameweek, entries)
            stored = 0
            for entry in missing:
                picks = await fpl.picks(entry, gameweek)
                if picks is None:
                    continue  # hidden or no Squad at that deadline: the Rival is left out
                await self._store.save(season, entry, picks)
                stored += 1
            if missing:
                log.info("rival picks stored for gameweek %d: %d", gameweek, stored)
