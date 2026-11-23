"""Runtime configuration, read from the environment only.

Required: ``TELEGRAM_BOT_TOKEN``, ``DATABASE_URL`` and ``OWNER_TELEGRAM_ID``. Everything else is
optional so a fork runs with nothing but a bot token and a Postgres URL.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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

        fixtures = env.get("FPL_FIXTURES_DIR", "").strip()
        return cls(
            telegram_bot_token=required("TELEGRAM_BOT_TOKEN"),
            database_url=required("DATABASE_URL"),
            owner_telegram_id=int(owner),
            fpl_source="fake" if source == "fake" else "live",
            fpl_fixtures_dir=Path(fixtures) if fixtures else None,
        )
