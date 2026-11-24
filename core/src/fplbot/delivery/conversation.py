"""What the bot says back to a private chat. Telegram-agnostic: text and button presses in,
replies out.

``telegram.py`` adapts python-telegram-bot updates to ``Conversation.respond`` and
``Conversation.press``; group chats never reach this module. Strangers get silence: an empty
reply list. Members are handed to ``MemberFlow`` (setup, settings, ``/leave``). Owner-only
commands (``/invite``, ``/accuracy``) get silence from anyone else, Members included.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from fplbot.advice.alert_time import UK
from fplbot.advice.price_accuracy import price_accuracy
from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.member_flow import GoalChanged, MemberFlow, SettingsChanged, TeamLinked
from fplbot.delivery.messages import Button, Incoming, Press, Reply
from fplbot.delivery.price_accuracy import render_accuracy
from fplbot.delivery.rate_limit import AttemptLimiter
from fplbot.delivery.rivals import RivalGaps
from fplbot.sources.fpl import FplSource
from fplbot.store.leagues import LeagueStore
from fplbot.store.members import Joined, MemberStore, Refusal
from fplbot.store.price_history import PriceHistoryStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore
from fplbot.store.watch_list import WatchListStore

__all__ = ["Button", "Conversation", "Incoming", "Press", "Reply"]

log = logging.getLogger(__name__)

INVITE_VALID_FOR = timedelta(hours=48)
MEMBER_CAP = 10
# After this many wrong codes in the window, a chat's further /start <code> attempts are ignored.
WRONG_CODES_ALLOWED = 5
WRONG_CODE_WINDOW = timedelta(hours=1)


class Conversation:
    def __init__(
        self,
        *,
        owner_id: int,
        members: MemberStore,
        watch_list: WatchListStore,
        fpl: FplSource,
        clock: Clock,
        reference: ReferenceStore,
        squads: SquadStore,
        leagues: LeagueStore,
        rival_gaps: RivalGaps,
        on_team_linked: TeamLinked,
        price_history: PriceHistoryStore,
        on_settings_changed: SettingsChanged = lambda: None,
        on_goal_changed: GoalChanged = lambda: None,
        owner_status: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self._owner_id = owner_id
        self._owner_status = owner_status
        self._members = members
        self._price_history = price_history
        self._clock = clock
        self._wrong_codes = AttemptLimiter(WRONG_CODES_ALLOWED, WRONG_CODE_WINDOW)
        self._member_flow = MemberFlow(
            members=members,
            watch_list=watch_list,
            fpl=fpl,
            clock=clock,
            reference=reference,
            squads=squads,
            leagues=leagues,
            rival_gaps=rival_gaps,
            on_team_linked=on_team_linked,
            on_settings_changed=on_settings_changed,
            on_goal_changed=on_goal_changed,
        )

    async def respond(self, message: Incoming, bot_username: str) -> list[Reply]:
        command, argument = _parse_command(message.text)
        now = self._clock.now()

        if command == "/invite" and message.user_id == self._owner_id:
            code = await self._members.issue_invite(now, INVITE_VALID_FOR)
            log.info("invite issued")
            hours = int(INVITE_VALID_FOR.total_seconds() // 3600)
            return [Reply(texts.invite_link(bot_username, code, hours))]

        # Before the Member lookup: /status must answer while the database is down.
        if command == "/status" and message.user_id == self._owner_id and self._owner_status:
            return [Reply(await self._owner_status())]

        if command == "/accuracy":
            if message.user_id != self._owner_id:
                return []
            return [Reply(await self._accuracy(now))]

        member = await self._members.get(message.chat_id)
        if member is not None:
            return await self._member_flow.on_text(member, command, argument)

        if command == "/start" and argument:
            return await self._redeem(argument, message.chat_id, now)
        return []

    async def press(self, press: Press) -> list[Reply]:
        member = await self._members.get(press.chat_id)
        if member is None:
            return []
        return await self._member_flow.on_press(member, press.data)

    async def _accuracy(self, now: datetime) -> str:
        season = season_of(now)
        # The latest night whose 00:00 UK price update has happened.
        last_night = now.astimezone(UK).date() - timedelta(days=1)
        outcomes = await self._price_history.outcomes(season)
        log.info("accuracy report shown")
        return render_accuracy(price_accuracy(outcomes, last_night=last_night), season)

    async def _redeem(self, code: str, chat_id: int, now: datetime) -> list[Reply]:
        if self._wrong_codes.is_locked(chat_id, now):
            log.info("invite attempt ignored: too many wrong codes")
            return []
        outcome = await self._members.redeem_invite(code, chat_id, now, member_cap=MEMBER_CAP)
        if isinstance(outcome, Joined):
            log.info("member %d joined", outcome.member_number)
            member = await self._members.get(chat_id)
            setup = await self._member_flow.begin(member) if member else []
            return [Reply(texts.GREETING), *setup]
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
