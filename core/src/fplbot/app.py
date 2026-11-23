"""Composition root: builds the running bot from config plus swappable edges.

Production passes only a ``Config``. The test harness also injects a fake clock, a fake FPL
transport and a fake Telegram request layer, and feeds updates through ``feed``, so tests drive
exactly the code that runs in production.
"""

import asyncio
import logging
from typing import Any, Self

from telegram import Update
from telegram.ext import Application
from telegram.request import BaseRequest

from fplbot.clock import Clock, SystemClock
from fplbot.config import Config, ConfigError
from fplbot.delivery import telegram
from fplbot.delivery.conversation import Conversation
from fplbot.sources.fake import DEFAULT_FIXTURES_DIR, FakeFplTransport
from fplbot.sources.fpl import FplSource, FplTransport
from fplbot.store.db import create_engine
from fplbot.store.members import MemberStore
from fplbot.store.watch_list import WatchListStore

log = logging.getLogger(__name__)


class FplBotApp:
    def __init__(
        self,
        config: Config,
        *,
        clock: Clock | None = None,
        fpl_transport: FplTransport | None = None,
        telegram_request: BaseRequest | None = None,
    ) -> None:
        self.clock: Clock = clock or SystemClock()
        self.engine = create_engine(config.database_url)
        self.members = MemberStore(self.engine)
        self.fpl = FplSource(fpl_transport or _fpl_transport_for(config))

        builder = Application.builder().token(config.telegram_bot_token)
        if telegram_request is not None:
            builder = builder.request(telegram_request).get_updates_request(telegram_request)
        self.telegram = builder.build()
        telegram.install(
            self.telegram,
            Conversation(
                owner_id=config.owner_telegram_id,
                members=self.members,
                watch_list=WatchListStore(self.engine),
                fpl=self.fpl,
                clock=self.clock,
            ),
        )

    async def __aenter__(self) -> Self:
        await self.telegram.initialize()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.telegram.shutdown()
        await self.engine.dispose()

    async def feed(self, update_data: dict[str, Any]) -> None:
        """Process one Telegram update (Bot API JSON) to completion."""
        update = Update.de_json(update_data, self.telegram.bot)
        await self.telegram.process_update(update)

    async def serve(self, stop: asyncio.Event) -> None:
        """Long-poll Telegram until ``stop`` is set."""
        await self.telegram.start()
        updater = self.telegram.updater
        if updater is None:
            raise RuntimeError("the Telegram application was built without an updater")
        await updater.start_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])
        log.info("polling")
        try:
            await stop.wait()
        finally:
            await updater.stop()
            await self.telegram.stop()


def _fpl_transport_for(config: Config) -> FplTransport:
    if config.fpl_source == "fake":
        return FakeFplTransport(config.fpl_fixtures_dir or DEFAULT_FIXTURES_DIR)
    raise ConfigError("the live FPL source is not built yet (ticket 27); set FPL_SOURCE=fake")
