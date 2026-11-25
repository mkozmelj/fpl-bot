"""Alembic environment. Migrations run synchronously over psycopg 3, online only."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from fplbot.store.db import sqlalchemy_url
from fplbot.store.schema import Base

config = context.config
database_url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(sqlalchemy_url(database_url), poolclass=NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
