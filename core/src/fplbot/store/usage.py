"""What the bot can read about its Neon usage without a Neon API key (ticket 23).

Storage: ``pg_database_size`` of the bot's own database, an ordinary SQL query. It is the logical
size, so it is a little below what Neon bills (Neon also counts history kept for restores), but
close enough for a 70% early warning. Compute hours are only in the Neon console and API (which
needs a key), so the bot does not read them; the runbook has a monthly check instead.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseUsage:
    def __init__(self, engine: AsyncEngine, storage_limit_bytes: int) -> None:
        self._engine = engine
        self.storage_limit_bytes = storage_limit_bytes

    async def size_bytes(self) -> int:
        """The database's size; raises if the database cannot be reached."""
        async with self._engine.connect() as connection:
            size = await connection.scalar(text("SELECT pg_database_size(current_database())"))
        return int(size or 0)
