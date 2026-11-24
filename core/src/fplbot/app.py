"""Composition root: builds the running bot from config plus swappable edges.

Production passes only a ``Config``. The test harness also injects a fake clock, a fake FPL
transport and a fake Telegram request layer, and feeds updates through ``feed``, so tests drive
exactly the code that runs in production.
"""

import asyncio
import logging
from importlib.metadata import version
from typing import Any, Self

from telegram import Update
from telegram.ext import Application
from telegram.request import BaseRequest

from fplbot.clock import Clock, SystemClock
from fplbot.config import Config
from fplbot.delivery import telegram, texts
from fplbot.delivery.conversation import Conversation
from fplbot.delivery.owner_alerts import OwnerAlerts
from fplbot.delivery.owner_chat import TelegramOwnerChat
from fplbot.delivery.status import OwnerStatus
from fplbot.jobs.backfill import JOB_NAME as BACKFILL_JOB
from fplbot.jobs.backfill import backfill_member
from fplbot.jobs.heartbeat import Heartbeat, HttpxPinger, Pinger
from fplbot.jobs.member_backup import (
    MEMBER_BACKUP_AT,
    MEMBER_BACKUP_JOB,
    MEMBER_BACKUP_ZONE,
    MemberBackup,
)
from fplbot.jobs.post_deadline import PostDeadline
from fplbot.jobs.price_alert import PriceAlerts
from fplbot.jobs.price_archive import PriceArchive
from fplbot.jobs.runner import JobRunner
from fplbot.jobs.scheduler import Scheduler, daily
from fplbot.jobs.storage_check import (
    STORAGE_CHECK_AT,
    STORAGE_CHECK_JOB,
    STORAGE_CHECK_ZONE,
    StorageCheck,
)
from fplbot.sources.fake import DEFAULT_FIXTURES_DIR, FakeFplTransport
from fplbot.sources.fpl import FplSource, FplTransport, PoliteFplClient, Priority
from fplbot.sources.live import HttpxFplTransport
from fplbot.store.completions import CompletionStore
from fplbot.store.db import create_engine
from fplbot.store.members import MemberStore
from fplbot.store.migrate import schema_is_current
from fplbot.store.owner_notices import OwnerNotices
from fplbot.store.price_history import PriceHistoryStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.squads import SquadStore
from fplbot.store.usage import DatabaseUsage
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
        heartbeat_pinger: Pinger | None = None,
    ) -> None:
        self.clock: Clock = clock or SystemClock()
        self.started_at = self.clock.now()
        self.config = config
        # "v0.1.0 (0123abc)": the package version and the deployed commit (ticket 38).
        self.version = texts.deploy_version(version("fplbot"), config.deploy_sha)
        self.engine = create_engine(config.database_url)
        self.completions = CompletionStore(self.engine)
        self.usage = DatabaseUsage(self.engine, config.database_storage_limit_mb * 1024 * 1024)
        self.status = OwnerStatus(
            clock=self.clock,
            started_at=self.started_at,
            version=self.version,
            completions=self.completions,
            usage=self.usage,
        )
        self.members = MemberStore(self.engine)
        self._live_fpl: HttpxFplTransport | None = None
        if fpl_transport is None:
            fpl_transport = self._fpl_transport_for(config)
        # Every FPL request in the process goes through this one client (one rate limit).
        self.fpl = FplSource(PoliteFplClient(fpl_transport, self.clock))
        # Reference data (Gameweeks, Footballers, clubs, fixtures) and Members' history/picks.
        self.reference = ReferenceStore(self.engine, self.clock)
        self.squads = SquadStore(self.engine)
        # Price snapshots, Price changes, alert-time codes and the news log (ticket 37).
        self.price_history = PriceHistoryStore(self.engine)

        def on_team_linked(member_number: int, team_id: int) -> None:
            job = backfill_member(
                member_number,
                team_id,
                reference=self.reference,
                squads=self.squads,
                clock=self.clock,
            )
            self.jobs.start(BACKFILL_JOB, job, Priority.ROUTINE)

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
                fpl=self.fpl.with_priority(Priority.INTERACTIVE),
                clock=self.clock,
                reference=self.reference,
                squads=self.squads,
                on_team_linked=on_team_linked,
                price_history=self.price_history,
                on_settings_changed=lambda: self.scheduler.rebuild(),
                owner_status=self.status.report,
            ),
        )

        owner_id = config.owner_telegram_id

        async def send_to_owner(text: str) -> None:
            await self.telegram.bot.send_message(owner_id, text)

        self._send_to_owner = send_to_owner

        self.owner_alerts = OwnerAlerts(send_to_owner, self.clock)
        self.jobs = JobRunner(self.fpl, self.owner_alerts)
        # Nightly job (ticket 39); ticket 31 schedules it, see jobs/member_backup.py.
        self.member_backup = MemberBackup(
            self.engine,
            config.backup_public_key,
            TelegramOwnerChat(self.telegram.bot, owner_id),
            self.clock,
        )

        async def send_to_member(chat_id: int, text: str) -> None:
            await self.telegram.bot.send_message(chat_id, text)

        # Nightly Price alerts: the scheduler runs ``planned_runs(night)`` (ticket 31).
        self.price_alerts = PriceAlerts(
            members=self.members,
            watch_list=WatchListStore(self.engine),
            squads=self.squads,
            owner_alerts=self.owner_alerts,
            clock=self.clock,
            send=send_to_member,
            price_history=self.price_history,
            completions=self.completions,
        )
        # Price snapshots, the nightly Price-change archive and the news log (ticket 37).
        self.price_archive = PriceArchive(
            history=self.price_history,
            completions=self.completions,
            reference=self.reference,
            clock=self.clock,
        )

        # Scheduled jobs: each feature adds a planner (see jobs/scheduler.py).
        self.scheduler = Scheduler(self.clock, self.jobs)
        self.post_deadline = PostDeadline(
            clock=self.clock,
            members=self.members,
            reference=self.reference,
            squads=self.squads,
            completions=self.completions,
        )
        self.scheduler.add(self.post_deadline.plan)
        self.scheduler.add(self.price_alerts.plan)
        self.scheduler.add(self.price_archive.plan)
        self.scheduler.add(
            daily(MEMBER_BACKUP_JOB, self.member_backup.run, MEMBER_BACKUP_AT, MEMBER_BACKUP_ZONE)
        )
        # Daily Neon storage cost guard (ticket 38): one owner DM past 70%.
        self.storage_check = StorageCheck(
            self.usage, OwnerNotices(self.engine), send_to_owner, self.clock
        )
        self.scheduler.add(
            daily(STORAGE_CHECK_JOB, self.storage_check.run, STORAGE_CHECK_AT, STORAGE_CHECK_ZONE)
        )

        # Liveness ping for the owner's monitor (ticket 38): only while the scheduler is alive.
        self._http_pinger: HttpxPinger | None = None
        if heartbeat_pinger is None and config.heartbeat_url is not None:
            heartbeat_pinger = self._http_pinger = HttpxPinger()
        self.heartbeat = Heartbeat(
            config.heartbeat_url,
            heartbeat_pinger,
            self.clock,
            healthy=lambda: self.scheduler.running,
        )

    def _fpl_transport_for(self, config: Config) -> FplTransport:
        if config.fpl_source == "fake":
            return FakeFplTransport(config.fpl_fixtures_dir or DEFAULT_FIXTURES_DIR, self.clock)
        self._live_fpl = HttpxFplTransport()
        return self._live_fpl

    async def __aenter__(self) -> Self:
        await self.telegram.initialize()
        return self

    def start_scheduling(self) -> None:
        """Start scheduled jobs (the startup refresh and catch-up, then the plan) and the
        heartbeat."""
        self.scheduler.start()
        self.heartbeat.start()

    async def __aexit__(self, *exc_info: object) -> None:
        await self.heartbeat.stop()
        await self.scheduler.stop()
        for task in list(self.jobs.running):
            task.cancel()
        await asyncio.gather(*self.jobs.running, return_exceptions=True)
        updater = self.telegram.updater
        if updater is not None and updater.running:
            await updater.stop()
        if self.telegram.running:
            await self.telegram.stop()
        await self.telegram.shutdown()
        await self.engine.dispose()
        if self._live_fpl is not None:
            await self._live_fpl.aclose()
        if self._http_pinger is not None:
            await self._http_pinger.aclose()

    async def feed(self, update_data: dict[str, Any]) -> None:
        """Process one Telegram update (Bot API JSON) to completion."""
        update = Update.de_json(update_data, self.telegram.bot)
        await self.telegram.process_update(update)

    async def start(self) -> None:
        """Production startup, in the order the smoke check relies on (ticket 23): the database
        is at the latest migration (Railway's pre-deploy ran it), the Telegram poll is up, the
        scheduler (and heartbeat) runs; then log ``ready sha=<commit>`` and DM the owner."""
        if not await schema_is_current(self.engine):
            log.error("startup aborted: the database is not at the latest migration")
            raise RuntimeError("the database is not at the latest migration")
        await self.telegram.start()
        updater = self.telegram.updater
        if updater is None:
            raise RuntimeError("the Telegram application was built without an updater")
        await updater.start_polling(allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY])
        self.start_scheduling()
        log.info("ready sha=%s", self.config.deploy_sha)
        try:
            await self._send_to_owner(texts.online(self.version))
        except Exception as error:  # Telegram hiccup: the bot is up anyway
            log.error("online DM failed: %s", type(error).__name__)

    async def serve(self, stop: asyncio.Event) -> None:
        """Start up, then long-poll Telegram until ``stop`` is set."""
        await self.start()
        await stop.wait()
