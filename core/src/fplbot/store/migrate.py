"""Run Alembic migrations programmatically (``python -m fplbot migrate``, the test harness).

The ``alembic`` CLI works too, from ``core/`` with ``DATABASE_URL`` set (see ``alembic.ini``).
"""

import logging

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import NullPool

from fplbot.store.db import sqlalchemy_url

log = logging.getLogger(__name__)

SCRIPT_LOCATION = "fplbot.store:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    # Passed as an attribute, not an ini option, so '%' in a password needs no escaping.
    config.attributes["database_url"] = database_url
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    """Migrate to ``revision``. A database a newer image already migrated further is left
    alone, so the pre-deploy command of a rolled-back image succeeds."""
    if is_ahead(_applied_revisions(database_url)):
        log.info("the database is ahead of this image (a rollback?): nothing to migrate")
        return
    command.upgrade(alembic_config(database_url), revision)


def _applied_revisions(database_url: str) -> set[str]:
    engine = create_engine(sqlalchemy_url(database_url), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()


def head_revisions() -> set[str]:
    """The revisions ``upgrade head`` leads to (one, unless migrations branched)."""
    return set(ScriptDirectory.from_config(alembic_config("")).get_heads())


def is_ahead(applied: set[str]) -> bool:
    """Whether the database was migrated past this code by a newer image: its revision is one
    this code doesn't know. After a rollback the previous image runs against that schema, which
    expand-only migrations (ADR 0003) keep compatible."""
    scripts = ScriptDirectory.from_config(alembic_config(""))
    known = {script.revision for script in scripts.walk_revisions()}
    return bool(applied) and not applied & known


async def schema_is_current(engine: AsyncEngine) -> bool:
    """Whether the database has been migrated to this code's head (the pre-deploy migration ran
    and succeeded), or past it by a newer image (a rollback). Checked at startup before the bot
    reports ready; a database behind this code is not current."""
    async with engine.connect() as connection:
        applied = set(await connection.scalars(text("SELECT version_num FROM alembic_version")))
    return applied == head_revisions() or is_ahead(applied)
