"""What the bot says back to a private chat. Telegram-agnostic: text in, replies out.

``telegram.py`` adapts python-telegram-bot updates to ``Conversation.respond``; group chats never
reach this module. Strangers get silence: an empty reply list.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.rate_limit import AttemptLimiter
from fplbot.store.members import Joined, MemberStore, Refusal

log = logging.getLogger(__name__)

INVITE_VALID_FOR = timedelta(hours=48)
MEMBER_CAP = 10
# After this many wrong codes in the window, a chat's further /start <code> attempts are ignored.
WRONG_CODES_ALLOWED = 5
WRONG_CODE_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class Reply:
    text: str


@dataclass(frozen=True)
class Incoming:
    """A text message in a private chat (where the chat ID equals the sender's user ID)."""

    chat_id: int
    user_id: int
    text: str


class Conversation:
    def __init__(self, *, owner_id: int, members: MemberStore, clock: Clock) -> None:
        self._owner_id = owner_id
        self._members = members
        self._clock = clock
        self._wrong_codes = AttemptLimiter(WRONG_CODES_ALLOWED, WRONG_CODE_WINDOW)

    async def respond(self, message: Incoming, bot_username: str) -> list[Reply]:
        command, argument = _parse_command(message.text)
        now = self._clock.now()

        if command == "/invite" and message.user_id == self._owner_id:
            code = await self._members.issue_invite(now, INVITE_VALID_FOR)
            log.info("invite issued")
            hours = int(INVITE_VALID_FOR.total_seconds() // 3600)
            return [Reply(texts.invite_link(bot_username, code, hours))]

        if await self._members.member_number(message.chat_id) is not None:
            # Setup, settings and the Member commands arrive with ticket 28.
            return [Reply(texts.WELCOME_BACK)] if command == "/start" else []

        if command == "/start" and argument:
            return await self._redeem(argument, message.chat_id, now)
        return []

    async def _redeem(self, code: str, chat_id: int, now: datetime) -> list[Reply]:
        if self._wrong_codes.is_locked(chat_id, now):
            log.info("invite attempt ignored: too many wrong codes")
            return []
        outcome = await self._members.redeem_invite(code, chat_id, now, member_cap=MEMBER_CAP)
        if isinstance(outcome, Joined):
            log.info("member %d joined", outcome.member_number)
            return [Reply(texts.GREETING)]
        log.info("invite refused: %s", outcome.value)
        if outcome is not Refusal.FULL:
            self._wrong_codes.record_failure(chat_id, now)
        refusal = _REFUSALS.get(outcome)
        return [Reply(refusal)] if refusal else []


# A real code that can't be used gets one short reply; a code that never existed gets silence.
_REFUSALS: dict[Refusal, str] = {
    Refusal.USED: texts.INVITE_USED,
    Refusal.EXPIRED: texts.INVITE_EXPIRED,
    Refusal.FULL: texts.bot_full(MEMBER_CAP),
}


def _parse_command(text: str) -> tuple[str | None, str]:
    """``"/start@SomeBot abc"`` -> ``("/start", "abc")``; plain text -> ``(None, text)``."""
    text = text.strip()
    if not text.startswith("/"):
        return None, text
    head, _, rest = text.partition(" ")
    return head.split("@", 1)[0].lower(), rest.strip()
