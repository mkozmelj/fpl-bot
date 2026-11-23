"""Test-session plumbing: a throwaway Postgres database and a running bot per test.

``TEST_DATABASE_URL`` is an admin URL for a disposable Postgres server. Each test session creates
its own uniquely named database there (several worktrees may share one server), migrates it to
head with Alembic, and drops it at the end. No secrets are involved.
"""

import os
import secrets
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import make_url

from fplbot.store import migrate
from tests.harness import BotHarness, running_bot


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.fail("Set TEST_DATABASE_URL to an admin URL of a throwaway Postgres server.")
    name = f"fplbot_test_{os.getpid()}_{secrets.token_hex(4)}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    try:
        migrate.upgrade(url)
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def empty_database(database_url: str) -> str:
    """The session database with every table emptied (schema and migrations kept)."""
    with psycopg.connect(database_url, autocommit=True) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ]
        if tables:
            connection.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(t) for t in tables)
                )
            )
    return database_url


@pytest.fixture
async def bot(empty_database: str) -> AsyncIterator[BotHarness]:
    async with running_bot(empty_database) as harness:
        yield harness
