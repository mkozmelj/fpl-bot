"""The one test seam: the delivery boundary.

A test drives the real bot (``FplBotApp``) the way Telegram and time would:

- ``chat.send(text)`` feeds a Telegram update into the bot and waits until it is handled;
- ``bot.advance(delta)`` moves the fake clock; once ``bot.start_scheduling()`` was called, the
  bot's scheduled jobs (``app.scheduler``) fire on the way, as they would in production;
- the fake FPL transport (``bot.fpl``) serves recorded fixtures from ``tests/fixtures/fpl``,
  and ``bot.fpl.respond(path, ...)`` scripts awkward answers (403, 429, 503 "updating");
- Postgres is real: a throwaway database per test session, emptied before every test.

Assert only on what chats receive (``chat.replies``), on what the owner is told, on log lines
(``bot.logs``) and on externally meaningful rows. Never on module calls, SQL or internal state.
"""

import asyncio
import heapq
import json
import logging
import re
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import Any

import pyrage
from sqlalchemy import text
from telegram.request import BaseRequest, RequestData

from fplbot import logs
from fplbot.app import FplBotApp
from fplbot.config import Config
from fplbot.jobs.runner import Job
from fplbot.sources.fake import FakeFplTransport
from fplbot.sources.fpl import FplResponse, Priority

OWNER_ID = 1000
# Real seconds the harness waits for the bot to finish work that is not on the fake clock
# (database I/O) before declaring it stuck.
SETTLE_TIMEOUT_SECONDS = 5.0
BOT_USERNAME = "FplTestBot"
# Every simulated sender is called this, so tests can check names never leak into logs.
SENDER_NAME = "Pseudonymia"
# Telegram lets a bot delete a message only while it is younger than this.
TELEGRAM_DELETE_WINDOW = timedelta(hours=48)
# The test bot's backup key pair (ticket 39): the bot encrypts to the public half, tests
# decrypt with the identity.
BACKUP_IDENTITY = pyrage.x25519.Identity.generate()
# A Thursday evening in the 2026-27 season, between Gameweeks.
DEFAULT_START = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)


class FakeClock:
    """Simulated time. ``sleep`` parks the caller until the harness moves time past its wake-up
    (``BotHarness.advance``, or automatically while a test waits on ``send`` / ``run_job``)."""

    def __init__(self, start: datetime = DEFAULT_START) -> None:
        self._now = start
        self._timers: list[tuple[datetime, int, asyncio.Future[None]]] = []
        self._order = count()
        self._sleeping: dict[asyncio.Task[Any], asyncio.Future[None]] = {}

    def now(self) -> datetime:
        return self._now

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        wake = asyncio.get_running_loop().create_future()
        heapq.heappush(
            self._timers, (self._now + timedelta(seconds=seconds), next(self._order), wake)
        )
        task = asyncio.current_task()
        assert task is not None
        self._sleeping[task] = wake
        try:
            await wake
        finally:
            self._sleeping.pop(task, None)

    def is_asleep(self, task: asyncio.Task[Any]) -> bool:
        wake = self._sleeping.get(task)
        return wake is not None and not wake.done()

    def next_wake_up(self) -> datetime | None:
        while self._timers and self._timers[0][2].done():  # cancelled sleeps
            heapq.heappop(self._timers)
        return self._timers[0][0] if self._timers else None

    def wake_next(self) -> None:
        """Move time to the earliest wake-up and wake that sleeper."""
        if self.next_wake_up() is None:
            return
        when, _, wake = heapq.heappop(self._timers)
        self._now = max(self._now, when)
        wake.set_result(None)

    def move_to(self, moment: datetime) -> None:
        self._now = max(self._now, moment)


@dataclass(frozen=True)
class BotApiCall:
    """One outgoing Telegram Bot API call, e.g. ``sendMessage`` with its parameters."""

    method: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class SentMessage:
    chat_id: int
    text: str
    message_id: int
    reply_markup: Any = None

    @property
    def buttons(self) -> list[str]:
        """The labels of this message's inline keyboard buttons, row by row."""
        return [button["text"] for _, button in self._inline_buttons()]

    def callback_data(self, label: str) -> str:
        for data, button in self._inline_buttons():
            if button["text"] == label:
                return data
        raise AssertionError(f"no button {label!r} in {self.buttons}")

    def _inline_buttons(self) -> list[tuple[str, Mapping[str, Any]]]:
        markup: Mapping[str, Any] = self.reply_markup or {}
        rows: list[list[Mapping[str, Any]]] = markup.get("inline_keyboard", [])
        return [(str(button["callback_data"]), button) for row in rows for button in row]


@dataclass(frozen=True)
class SentDocument:
    """A file the bot sent (``sendDocument``), with its bytes as uploaded."""

    chat_id: int
    message_id: int
    filename: str
    content: bytes
    caption: str | None = None


class FakeTelegram(BaseRequest):
    """Stands in for python-telegram-bot's HTTP layer: records every Bot API call and answers
    with plausible results, so the real PTB ``Application`` runs offline."""

    def __init__(self, clock: FakeClock) -> None:
        self.calls: list[BotApiCall] = []
        self.sent_messages: list[SentMessage] = []
        self.sent_documents: list[SentDocument] = []
        # (chat_id, message_id) of messages gone from the chat: removed by the bot
        # (``deleteMessage``) or by the user (``delete_by_hand``).
        self.deleted: set[tuple[int, int]] = set()
        self._clock = clock
        self._message_ids = count(1)
        self._sent_at: dict[tuple[int, int], datetime] = {}

    def delete_by_hand(self, chat_id: int, message_id: int) -> None:
        """The user deletes one of the bot's messages in their chat; editing it then fails."""
        self.deleted.add((chat_id, message_id))

    def _new_message_id(self, chat_id: int) -> int:
        message_id = next(self._message_ids)
        self._sent_at[chat_id, message_id] = self._clock.now()
        return message_id

    def _deletable(self, params: Mapping[str, Any]) -> bool:
        """Telegram lets a bot delete a message only while it is under 48 hours old."""
        sent_at = self._sent_at.get((int(params["chat_id"]), int(params["message_id"])))
        return sent_at is not None and self._clock.now() - sent_at < TELEGRAM_DELETE_WINDOW

    @property
    def read_timeout(self) -> float | None:
        return None

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: RequestData | None = None,
        read_timeout: Any = None,
        write_timeout: Any = None,
        connect_timeout: Any = None,
        pool_timeout: Any = None,
    ) -> tuple[int, bytes]:
        api_method = url.rsplit("/", 1)[-1]
        params: dict[str, Any] = dict(request_data.parameters) if request_data else {}
        self.calls.append(BotApiCall(api_method, params))
        if api_method == "deleteMessage" and not self._deletable(params):
            return _bad_request("message can't be deleted for everyone")
        if request_data is not None and api_method in ("sendDocument", "editMessageMedia"):
            if api_method == "sendDocument":
                sent = self._new_document(request_data)
            elif (sent := self._edited_document(request_data)) is None:
                return _bad_request("message to edit not found")
            return 200, json.dumps({"ok": True, "result": self._document_json(sent)}).encode()
        return 200, json.dumps({"ok": True, "result": self._result(api_method, params)}).encode()

    def _new_document(self, request_data: RequestData) -> SentDocument:
        params = request_data.parameters
        filename, content = self._upload(request_data)
        chat_id = int(str(params["chat_id"]))
        sent = SentDocument(
            chat_id=chat_id,
            message_id=self._new_message_id(chat_id),
            filename=filename,
            content=content,
            caption=str(params["caption"]) if "caption" in params else None,
        )
        self.sent_documents.append(sent)
        return sent

    def _edited_document(self, request_data: RequestData) -> SentDocument | None:
        """``editMessageMedia`` replacing a document the bot sent; None if it is not there."""
        params = request_data.parameters
        where = (int(str(params["chat_id"])), int(str(params["message_id"])))
        media: Any = params["media"]
        if isinstance(media, str):
            media = json.loads(media)
        for index, old in enumerate(self.sent_documents):
            if (old.chat_id, old.message_id) == where and where not in self.deleted:
                filename, content = self._upload(request_data)
                caption = media.get("caption")
                self.sent_documents[index] = edited = replace(
                    old, filename=filename, content=content, caption=caption
                )
                return edited
        return None

    @staticmethod
    def _upload(request_data: RequestData) -> tuple[str, bytes]:
        (filename, content, *_), *_ = request_data.multipart_data.values()
        return str(filename), content if isinstance(content, bytes) else content.read()

    @staticmethod
    def _document_json(sent: SentDocument) -> dict[str, Any]:
        return {
            "message_id": sent.message_id,
            "date": 0,
            "chat": {"id": sent.chat_id, "type": "private"},
            "document": {"file_id": f"file-{sent.message_id}", "file_unique_id": "u"},
            "caption": sent.caption,
        }

    def _result(self, api_method: str, params: Mapping[str, Any]) -> Any:
        if api_method == "getMe":
            return {"id": 1, "is_bot": True, "first_name": "FPL test bot", "username": BOT_USERNAME}
        if api_method == "deleteMessage":
            self.deleted.add((int(params["chat_id"]), int(params["message_id"])))
            return True
        if api_method == "sendMessage":
            chat_id = int(params["chat_id"])
            sent = SentMessage(
                chat_id=chat_id,
                text=str(params["text"]),
                message_id=self._new_message_id(chat_id),
                reply_markup=params.get("reply_markup"),
            )
            self.sent_messages.append(sent)
            return {
                "message_id": sent.message_id,
                "date": 0,
                "chat": {"id": sent.chat_id, "type": "private"},
                "text": sent.text,
            }
        return True


def _bad_request(description: str) -> tuple[int, bytes]:
    error = {"ok": False, "error_code": 400, "description": f"Bad Request: {description}"}
    return 400, json.dumps(error).encode()


@dataclass
class Chat:
    """A Telegram chat as seen by one user: send text in, read what the bot sent back."""

    harness: BotHarness
    chat_id: int
    user_id: int
    kind: str = "private"

    async def send(self, text: str) -> None:
        await self.harness.deliver_text(self, text)

    async def press(self, label: str, on: SentMessage | None = None) -> None:
        """Tap the inline button ``label`` on message ``on``; by default on the latest message
        that offers a button with that label. Pass an older message to tap a stale keyboard."""
        if on is None:
            offering = [m for m in self.messages if label in m.buttons]
            assert offering, f"no message in chat {self.chat_id} offers {label!r}"
            on = offering[-1]
        await self.harness.deliver_press(self, on, on.callback_data(label))

    @property
    def messages(self) -> list[SentMessage]:
        return [m for m in self.harness.telegram.sent_messages if m.chat_id == self.chat_id]

    @property
    def last_message(self) -> SentMessage:
        messages = self.messages
        assert messages, f"chat {self.chat_id} received nothing"
        return messages[-1]

    @property
    def documents(self) -> list[SentDocument]:
        """Files the bot sent to this chat that are still there (not deleted)."""
        telegram = self.harness.telegram
        return [
            document
            for document in telegram.sent_documents
            if document.chat_id == self.chat_id
            and (document.chat_id, document.message_id) not in telegram.deleted
        ]

    @property
    def replies(self) -> list[str]:
        return [m.text for m in self.messages]

    @property
    def last_reply(self) -> str:
        replies = self.replies
        assert replies, f"chat {self.chat_id} received nothing"
        return replies[-1]


@dataclass
class BotHarness:
    app: FplBotApp
    config: Config
    clock: FakeClock
    telegram: FakeTelegram
    fpl: FakeFplTransport
    logs: list[str] = field(default_factory=list[str])
    _update_ids: count[int] = field(default_factory=lambda: count(1))
    _driven: set[asyncio.Task[Any]] = field(default_factory=set[asyncio.Task[Any]])
    _scheduling: bool = False

    @property
    def owner(self) -> Chat:
        return self.private_chat(OWNER_ID)

    def private_chat(self, user_id: int) -> Chat:
        return Chat(self, chat_id=user_id, user_id=user_id)

    def group_chat(self, chat_id: int, user_id: int) -> Chat:
        return Chat(self, chat_id=chat_id, user_id=user_id, kind="group")

    async def advance(self, delta: timedelta) -> None:
        """Let ``delta`` of simulated time pass, waking every sleeper due on the way, in order,
        and letting the bot run in between (rate-limit waits, backoff, background jobs)."""
        target = self.clock.now() + delta
        await self._settle()
        while (wake := self.clock.next_wake_up()) is not None and wake <= target:
            self.clock.wake_next()
            await self._settle()
        self.clock.move_to(target)

    async def start_scheduling(self) -> None:
        """Start the bot's scheduled jobs as production does at startup (startup refresh and
        catch-up first, then the plan), and keep them running across ``restart``. Off by default
        so tests that script FPL answers are not disturbed by scheduled fetches."""
        self._scheduling = True
        self.app.start_scheduling()
        await self._settle()

    def start_job(self, name: str, job: Job, priority: Priority = Priority.ROUTINE) -> None:
        """Start a job in the background; it runs as ``advance`` moves time."""
        self.app.jobs.start(name, job, priority)

    async def run_job(self, name: str, job: Job, priority: Priority = Priority.ROUTINE) -> bool:
        """Run a job to the end, moving simulated time on whenever it waits; ``True`` if it
        succeeded."""
        return await self._until_done(self.app.jobs.start(name, job, priority))

    async def _until_done[T](self, task: asyncio.Task[T]) -> T:
        self._driven.add(task)
        try:
            while True:
                await self._settle()
                if task.done():
                    return task.result()
                if self.clock.next_wake_up() is None:
                    raise AssertionError("the bot is stuck on something the clock cannot wake")
                self.clock.wake_next()
        finally:
            self._driven.discard(task)

    async def _settle(self) -> None:
        """Run the bot until all work in flight is finished or asleep on the fake clock."""
        loop = asyncio.get_running_loop()
        give_up = loop.time() + SETTLE_TIMEOUT_SECONDS
        while True:
            for _ in range(5):
                await asyncio.sleep(0)
            busy = self._awake_work()
            if not busy:
                return
            if loop.time() > give_up:
                raise AssertionError("the bot did not settle: something waits outside the clock")
            await asyncio.wait(busy, timeout=0.01)

    def _awake_work(self) -> list[asyncio.Task[Any]]:
        """Tasks doing the bot's work (jobs, updates being handled, and the tasks they await)
        that are neither asleep on the fake clock nor waiting only on tasks that are."""
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        awaited: dict[asyncio.Task[Any], set[asyncio.Task[Any]]] = {task: set() for task in tasks}
        for task in tasks:
            graph = asyncio.capture_call_graph(task)
            for waiter in graph.awaited_by if graph else ():
                if isinstance(waiter.future, asyncio.Task) and waiter.future in awaited:
                    awaited[waiter.future].add(task)

        work = {
            task
            for task in (*self.app.jobs.running, *self.app.scheduler.tasks, *self._driven)
            if not task.done()
        }
        # Waiting for a held lock counts as parked: the holder is either awake work itself
        # (so we keep settling) or asleep on the clock (so time has to move on).
        parked = {task for task in tasks if self.clock.is_asleep(task) or _waiting_for_lock(task)}
        changed = True
        while changed:
            changed = False
            for task in tasks:
                if task in work and not awaited[task] <= work:
                    work |= awaited[task]
                    changed = True
                if task not in parked and awaited[task] and awaited[task] <= parked:
                    parked.add(task)
                    changed = True
        return [task for task in work if task not in parked]

    async def restart(self, config: Config | None = None) -> None:
        """Stop the bot and start a fresh process against the same database, clock, Telegram
        and FPL fakes: anything held only in memory is gone. Pass ``config`` to start it with
        other settings (e.g. ``dataclasses.replace(bot.config, backup_public_key=None)``)."""
        await self.app.__aexit__(None, None, None)
        if config is not None:
            self.config = config
        self.app = FplBotApp(
            self.config, clock=self.clock, fpl_transport=self.fpl, telegram_request=self.telegram
        )
        await self.app.__aenter__()
        if self._scheduling:
            self.app.start_scheduling()
            await self._settle()

    async def invited_friend(self, user_id: int) -> Chat:
        """A friend who has just redeemed an owner's invite: allow-listed, setup not started."""
        await self.owner.send("/invite")
        friend = self.private_chat(user_id)
        await friend.send(f"/start {start_code_in(self.owner.last_reply)}")
        return friend

    async def active_member(
        self, user_id: int, team_id: int, timezone: str = "Europe/London"
    ) -> Chat:
        """A Member who finished setup through the real flow: ``team_id`` linked (it needs a
        fixture under ``entry/``), Goal Overall rank, ``timezone`` (one of the four buttons)."""
        member = await self.invited_friend(user_id)
        await member.send(str(team_id))
        await member.press("Yes, that's me")
        await member.press("Overall rank")
        await member.press(timezone)
        assert member.last_reply.startswith("You're all set"), member.last_reply
        return member

    async def deliver_text(self, chat: Chat, text_: str) -> None:
        update_id = next(self._update_ids)
        message: dict[str, Any] = {
            "message_id": update_id,
            "date": int(self.clock.now().timestamp()),
            "chat": _chat_json(chat),
            "from": _sender_json(chat),
            "text": text_,
        }
        if command := re.match(r"/\S+", text_):
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": command.end()}]
        update = {"update_id": update_id, "message": message}
        await self._until_done(asyncio.create_task(self.app.feed(update)))

    async def deliver_press(self, chat: Chat, on: SentMessage, callback_data: str) -> None:
        """Feed a ``callback_query`` update: ``chat``'s user tapped a button on message ``on``."""
        update_id = next(self._update_ids)
        query: dict[str, Any] = {
            "id": f"query-{update_id}",
            "from": _sender_json(chat),
            "chat_instance": f"instance-{chat.chat_id}",
            "data": callback_data,
            "message": {
                "message_id": on.message_id,
                "date": 0,
                "chat": _chat_json(chat),
                "from": {"id": 1, "is_bot": True, "first_name": "FPL test bot"},
                "text": on.text,
                "reply_markup": on.reply_markup,
            },
        }
        update = {"update_id": update_id, "callback_query": query}
        await self._until_done(asyncio.create_task(self.app.feed(update)))

    async def database_text(self) -> str:
        """Every row of every table, as text: for checking what is (not) stored."""
        dump: list[str] = []
        async with self.app.engine.connect() as connection:
            tables = await connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            for table in tables.all():
                rows = await connection.execute(text(f'SELECT * FROM "{table}"'))  # noqa: S608
                dump.extend(f"{table}: {tuple(row)}" for row in rows)
        return "\n".join(dump)


FPL_FIXTURES = Path(__file__).parent / "fixtures" / "fpl"
FPL_RESPONSES = Path(__file__).parent / "fixtures" / "fpl-responses"


def fpl_fixture(path: str) -> FplResponse:
    """A 200 answer with the recorded fixture for an API path, e.g. ``bootstrap-static/``."""
    body = (FPL_FIXTURES / f"{path.strip('/')}.json").read_bytes()
    return FplResponse(200, body, {"content-type": "application/json"})


def canned_fpl_response(name: str) -> FplResponse:
    """An awkward FPL answer from ``fixtures/fpl-responses/<name>.json``: ``503-updating``,
    ``403-forbidden``, ``429-retry-after``, ``502-bad-gateway``,
    ``bootstrap-static-missing-fields``. Each file holds a status, headers and a body (text)
    or json."""
    spec = json.loads((FPL_RESPONSES / f"{name}.json").read_text())
    body = json.dumps(spec["json"]) if "json" in spec else spec["body"]
    return FplResponse(spec["status"], body.encode(), spec.get("headers", {}))


def _waiting_for_lock(task: asyncio.Task[Any]) -> bool:
    """Whether ``task`` is blocked in ``asyncio.Lock.acquire`` on a lock someone still holds
    (e.g. an interactive command waiting for the shared ``bootstrap-static`` fetch of a job)."""
    graph = asyncio.capture_call_graph(task)
    if graph is None or not graph.call_stack:
        return False
    frame = graph.call_stack[0].frame
    lock = frame.f_locals.get("self")
    return frame.f_code.co_name == "acquire" and isinstance(lock, asyncio.Lock) and lock.locked()


def _chat_json(chat: Chat) -> dict[str, Any]:
    if chat.kind == "private":
        return {"id": chat.chat_id, "type": "private", "first_name": SENDER_NAME}
    return {"id": chat.chat_id, "type": chat.kind, "title": "Test group"}


def _sender_json(chat: Chat) -> dict[str, Any]:
    return {"id": chat.user_id, "is_bot": False, "first_name": SENDER_NAME}


def start_code_in(invite_reply: str) -> str:
    """The code from an invite reply's ``t.me/<bot>?start=<code>`` link."""
    match = re.search(rf"https://t\.me/{BOT_USERNAME}\?start=([A-Za-z0-9_-]+)", invite_reply)
    assert match, f"no start link in {invite_reply!r}"
    return match.group(1)


class _ListHandler(logging.Handler):
    def __init__(self, sink: list[str]) -> None:
        super().__init__(logging.INFO)
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(f"{record.name} {record.getMessage()}")


@asynccontextmanager
async def running_bot(database_url: str) -> AsyncGenerator[BotHarness]:
    config = Config.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "123456:TEST-TOKEN",
            "DATABASE_URL": database_url,
            "OWNER_TELEGRAM_ID": str(OWNER_ID),
            "FPL_SOURCE": "fake",
            "BACKUP_AGE_PUBLIC_KEY": str(BACKUP_IDENTITY.to_public()),
        }
    )
    clock = FakeClock()
    telegram = FakeTelegram(clock)
    fpl = FakeFplTransport(clock=clock)
    app = FplBotApp(config, clock=clock, fpl_transport=fpl, telegram_request=telegram)
    harness = BotHarness(app=app, config=config, clock=clock, telegram=telegram, fpl=fpl)

    root = logging.getLogger()
    previous_level = root.level
    handler = _ListHandler(harness.logs)
    logs.configure()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        await app.__aenter__()
        try:
            yield harness
        finally:
            await harness.app.__aexit__(None, None, None)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)
