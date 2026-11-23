"""Logging setup. Logs may carry an internal Member number only: never chat IDs, team IDs or
names. Our own log lines follow that rule; noisy third-party loggers are turned down here."""

import logging


def configure(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs every request URL at INFO, and Telegram Bot API URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
