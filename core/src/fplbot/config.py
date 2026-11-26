"""Runtime configuration, read from the environment only.

Required: ``TELEGRAM_BOT_TOKEN``, ``DATABASE_URL`` and ``OWNER_TELEGRAM_ID``. Everything else is
optional so a fork runs with nothing but a bot token and a Postgres URL.

The deployed commit comes from ``GIT_SHA`` (a build argument, for local builds), else Railway's
``RAILWAY_GIT_COMMIT_SHA`` (set for deploys triggered from the GitHub repo, which is how
production deploys; ADR 0004), else ``"unknown"``. An empty ``GIT_SHA`` counts as unset. It is
what the ``ready sha=<commit>`` startup line carries.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pyrage

FplSourceKind = Literal["live", "fake"]


class ConfigError(Exception):
    """The environment is missing or has a malformed setting. The message names the variable."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str = field(repr=False)
    database_url: str = field(repr=False)
    owner_telegram_id: int
    # "fake" serves recorded fixtures from ``fpl_fixtures_dir`` instead of calling FPL.
    fpl_source: FplSourceKind = "live"
    fpl_fixtures_dir: Path | None = None
    # The age public key (``age1...``) the nightly Member backup is encrypted to; its private
    # key lives only in the owner's password manager. None: no backup, and the owner is told.
    backup_public_key: str | None = None
    # Pinged every 5 minutes while the bot is healthy (the owner's uptime monitor). None: no pings.
    heartbeat_url: str | None = field(default=None, repr=False)
    # The deployed commit, logged as ``ready sha=<commit>`` once the bot is up.
    deploy_sha: str = "unknown"
    # The database storage the plan allows (Neon Free: 1 GB per project); the owner is told once
    # when the database passes 70% of it.
    database_storage_limit_mb: int = 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Config:
        def required(name: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise ConfigError(f"{name} is not set")
            return value

        owner = required("OWNER_TELEGRAM_ID")
        if not owner.isdigit():
            raise ConfigError("OWNER_TELEGRAM_ID must be a numeric Telegram user ID")

        source = env.get("FPL_SOURCE", "live").strip() or "live"
        if source not in ("live", "fake"):
            raise ConfigError("FPL_SOURCE must be 'live' or 'fake'")

        backup_key = env.get("BACKUP_AGE_PUBLIC_KEY", "").strip() or None
        if backup_key is not None:
            try:
                pyrage.x25519.Recipient.from_str(backup_key)
            except pyrage.RecipientError:
                raise ConfigError(
                    "BACKUP_AGE_PUBLIC_KEY must be an age public key (age1...)"
                ) from None

        heartbeat_url = env.get("HEARTBEAT_URL", "").strip() or None
        if heartbeat_url is not None and not heartbeat_url.startswith(("https://", "http://")):
            raise ConfigError("HEARTBEAT_URL must be an http:// or https:// URL")

        storage_limit = env.get("DATABASE_STORAGE_LIMIT_MB", "").strip() or "1024"
        if not storage_limit.isdigit() or int(storage_limit) == 0:
            raise ConfigError("DATABASE_STORAGE_LIMIT_MB must be a positive whole number")

        sha = (
            env.get("GIT_SHA", "").strip()
            or env.get("RAILWAY_GIT_COMMIT_SHA", "").strip()
            or "unknown"
        )

        fixtures = env.get("FPL_FIXTURES_DIR", "").strip()
        return cls(
            telegram_bot_token=required("TELEGRAM_BOT_TOKEN"),
            database_url=required("DATABASE_URL"),
            owner_telegram_id=int(owner),
            fpl_source="fake" if source == "fake" else "live",
            fpl_fixtures_dir=Path(fixtures) if fixtures else None,
            backup_public_key=backup_key,
            heartbeat_url=heartbeat_url,
            deploy_sha=sha,
            database_storage_limit_mb=int(storage_limit),
        )
