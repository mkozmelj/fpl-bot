"""Engine construction. One place decides how we talk to Postgres (Neon in production)."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


def sqlalchemy_url(database_url: str) -> str:
    """Accept a plain ``postgres://`` / ``postgresql://`` URL (as Neon gives it) and pin the
    psycopg 3 driver, which serves both the async app and the sync Alembic migrations."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg://" + database_url.removeprefix(prefix)
    raise ValueError("DATABASE_URL must be a postgres:// or postgresql:// URL")


def create_engine(database_url: str) -> AsyncEngine:
    # NullPool: no idle connections are held, so Neon can scale to zero between bursts. Neon's
    # pooled endpoint does the pooling. Prepared statements are off for the same pooler.
    return create_async_engine(
        sqlalchemy_url(database_url),
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )
