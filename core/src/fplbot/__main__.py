"""Entry point.

python -m fplbot migrate   # alembic upgrade head (Railway pre-deploy, ADR 0003)
python -m fplbot           # run the bot (Telegram long polling)
"""

import asyncio
import os
import signal
import sys

from fplbot import logs
from fplbot.app import FplBotApp
from fplbot.config import Config, ConfigError
from fplbot.store import migrate


async def _run(config: Config) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    async with FplBotApp(config) as app:
        await app.serve(stop)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    logs.configure()
    try:
        config = Config.from_env(os.environ)
        if args == ["migrate"]:
            migrate.upgrade(config.database_url)
        elif not args:
            asyncio.run(_run(config))
        else:
            print("usage: python -m fplbot [migrate]", file=sys.stderr)
            return 2
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
