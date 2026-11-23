"""The one test seam: the delivery boundary.

A test drives the real bot (``FplBotApp``) the way Telegram and time would:

- ``chat.send(text)`` feeds a Telegram update into the bot and waits until it is handled;
- ``bot.advance(delta)`` moves the fake clock (scheduled-job ticks hook in here, ticket 31);
- the fake FPL transport (``bot.fpl``) serves recorded fixtures from ``tests/fixtures/fpl``,
  and ``bot.fpl.respond(path, ...)`` scripts awkward answers (403, 429, 503 "updating");
- Postgres is real: a throwaway database per test session, emptied before every test.

Assert only on what chats receive (``chat.replies``), on what the owner is told, on log lines
(``bot.logs``) and on externally meaningful rows. Never on module calls, SQL or internal state.
"""

import json
import logging
import re
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

from sqlalchemy import text
from telegram.request import BaseRequest, RequestData

from fplbot import logs
from fplbot.app import FplBotApp
from fplbot.config import Config
from fplbot.sources.fake import FakeFplTransport

OWNER_ID = 1000
BOT_USERNAME = "FplTestBot"
# Every simulated sender is called this, so tests can check names never leak into logs.
SENDER_NAME = "Pseudonymia"
# A Thursday evening in the 2026-27 season, between Gameweeks.
DEFAULT_START = datetime(2026, 11, 19, 18, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, start: datetime = DEFAULT_START) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


@dataclass(frozen=True)
class BotApiCall:
    """One outgoing Telegram Bot API call, e.g. ``sendMessage`` with its parameters."""

    method: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class SentMessage:
    chat_id: int
    text: str
    reply_markup: Any = None


class FakeTelegram(BaseRequest):
    """Stands in for python-telegram-bot's HTTP layer: records every Bot API call and answers
    with plausible results, so the real PTB ``Application`` runs offline."""

    def __init__(self) -> None:
        self.calls: list[BotApiCall] = []
        self._message_ids = count(1)

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
        return 200, json.dumps({"ok": True, "result": self._result(api_method, params)}).encode()

    def _result(self, api_method: str, params: Mapping[str, Any]) -> Any:
        if api_method == "getMe":
            return {"id": 1, "is_bot": True, "first_name": "FPL test bot", "username": BOT_USERNAME}
        if api_method == "sendMessage":
            return {
                "message_id": next(self._message_ids),
                "date": 0,
                "chat": {"id": int(params["chat_id"]), "type": "private"},
                "text": params["text"],
            }
        return True

    @property
    def sent_messages(self) -> list[SentMessage]:
        return [
            SentMessage(
                int(c.params["chat_id"]), str(c.params["text"]), c.params.get("reply_markup")
            )
            for c in self.calls
            if c.method == "sendMessage"
        ]


@dataclass
class Chat:
    """A Telegram chat as seen by one user: send text in, read what the bot sent back."""

    harness: BotHarness
    chat_id: int
    user_id: int
    kind: str = "private"

    async def send(self, text: str) -> None:
        await self.harness.deliver_text(self, text)

    @property
    def replies(self) -> list[str]:
        return [m.text for m in self.harness.telegram.sent_messages if m.chat_id == self.chat_id]

    @property
    def last_reply(self) -> str:
        replies = self.replies
        assert replies, f"chat {self.chat_id} received nothing"
        return replies[-1]


@dataclass
class BotHarness:
    app: FplBotApp
    clock: FakeClock
    telegram: FakeTelegram
    fpl: FakeFplTransport
    logs: list[str] = field(default_factory=list[str])
    _update_ids: count[int] = field(default_factory=lambda: count(1))

    @property
    def owner(self) -> Chat:
        return self.private_chat(OWNER_ID)

    def private_chat(self, user_id: int) -> Chat:
        return Chat(self, chat_id=user_id, user_id=user_id)

    def group_chat(self, chat_id: int, user_id: int) -> Chat:
        return Chat(self, chat_id=chat_id, user_id=user_id, kind="group")

    async def advance(self, delta: timedelta) -> None:
        self.clock.advance(delta)

    async def deliver_text(self, chat: Chat, text_: str) -> None:
        update_id = next(self._update_ids)
        chat_json: dict[str, Any] = {"id": chat.chat_id, "type": chat.kind}
        chat_json |= (
            {"first_name": SENDER_NAME} if chat.kind == "private" else {"title": "Test group"}
        )
        message: dict[str, Any] = {
            "message_id": update_id,
            "date": int(self.clock.now().timestamp()),
            "chat": chat_json,
            "from": {"id": chat.user_id, "is_bot": False, "first_name": SENDER_NAME},
            "text": text_,
        }
        if command := re.match(r"/\S+", text_):
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": command.end()}]
        await self.app.feed({"update_id": update_id, "message": message})

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
        }
    )
    clock, telegram, fpl = FakeClock(), FakeTelegram(), FakeFplTransport()
    app = FplBotApp(config, clock=clock, fpl_transport=fpl, telegram_request=telegram)
    harness = BotHarness(app=app, clock=clock, telegram=telegram, fpl=fpl)

    root = logging.getLogger()
    previous_level = root.level
    handler = _ListHandler(harness.logs)
    logs.configure()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        async with app:
            yield harness
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)
