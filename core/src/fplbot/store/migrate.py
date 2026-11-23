"""Run Alembic migrations programmatically (``python -m fplbot migrate``, the test harness).

The ``alembic`` CLI works too, from ``core/`` with ``DATABASE_URL`` set (see ``alembic.ini``).
"""

from alembic import command
from alembic.config import Config

SCRIPT_LOCATION = "fplbot.store:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    # Passed as an attribute, not an ini option, so '%' in a password needs no escaping.
    config.attributes["database_url"] = database_url
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)
