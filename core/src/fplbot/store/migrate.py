"""Run Alembic migrations programmatically (``python -m fplbot migrate``, the test harness).

The ``alembic`` CLI works too, from ``core/`` with ``DATABASE_URL`` set (see ``alembic.ini``).
"""

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

SCRIPT_LOCATION = "fplbot.store:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    # Passed as an attribute, not an ini option, so '%' in a password needs no escaping.
    config.attributes["database_url"] = database_url
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def head_revisions() -> set[str]:
    """The revisions ``upgrade head`` leads to (one, unless migrations branched)."""
    return set(ScriptDirectory.from_config(alembic_config("")).get_heads())


async def schema_is_current(engine: AsyncEngine) -> bool:
    """Whether the database has been migrated to this code's head (the pre-deploy migration ran
    and succeeded). Checked at startup before the bot reports ready."""
    async with engine.connect() as connection:
        applied = await connection.scalars(text("SELECT version_num FROM alembic_version"))
        return set(applied) == head_revisions()
