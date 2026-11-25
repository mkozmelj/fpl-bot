"""The owner's ``/rollover`` (ticket 40): start the new season FPL already shows, once confirmed.

``/rollover`` asks for confirmation with two buttons; only the latest keyboard counts, once.
Confirming starts the new season (``Seasons.roll_over``), then asks every active Member once to
reconfirm their Goal and league (the ticket 28 Goal question). With no new season waiting, as
after a first rollover, ``/rollover`` changes nothing.
"""

import logging
import secrets
from collections.abc import Awaitable, Callable

from fplbot.delivery import texts
from fplbot.delivery.messages import Button, Reply
from fplbot.store.members import MemberRecord, MemberStore
from fplbot.store.seasons import Seasons

log = logging.getLogger(__name__)

_PREFIX = "rollover:"

# Sends replies (with their keyboards) to a chat outside an update: the Goal prompts.
type SendReplies = Callable[[int, list[Reply]], Awaitable[None]]
# The Goal question for a Member (it opens their chat's Goal step), for a season.
type AskGoalAgain = Callable[[MemberRecord, str], list[Reply]]


class OwnerRollover:
    def __init__(
        self,
        *,
        seasons: Seasons,
        members: MemberStore,
        ask_goal_again: AskGoalAgain,
        send: SendReplies,
        on_rolled_over: Callable[[], None],
    ) -> None:
        self._seasons = seasons
        self._members = members
        self._ask_goal_again = ask_goal_again
        self._send = send
        self._on_rolled_over = on_rolled_over
        self._keyboard: str | None = None

    @staticmethod
    def owns(data: str) -> bool:
        """Whether a button press belongs to a rollover confirmation."""
        return data.startswith(_PREFIX)

    def ask(self) -> list[Reply]:
        waiting = self._seasons.waiting
        if waiting is None:
            self._keyboard = None
            return [Reply(texts.rollover_nothing_waiting(self._seasons.current))]
        self._keyboard = secrets.token_hex(4)
        data = f"{_PREFIX}{self._keyboard}:"
        buttons = (
            Button(texts.rollover_confirm_button(waiting), data + "yes"),
            Button(texts.ROLLOVER_CANCEL_BUTTON, data + "no"),
        )
        return [Reply(texts.rollover_ask(waiting, self._seasons.current), (buttons,))]

    async def press(self, data: str) -> list[Reply]:
        token, _, choice = data.removeprefix(_PREFIX).partition(":")
        if self._keyboard is None or token != self._keyboard:
            return [Reply(texts.STALE_BUTTON)]
        self._keyboard = None
        if choice != "yes":
            return [Reply(texts.ROLLOVER_CANCELLED)]
        rollover = await self._seasons.roll_over()
        if rollover is None:
            return [Reply(texts.rollover_nothing_waiting(self._seasons.current))]
        self._on_rolled_over()
        members = await self._members.active()
        for member in members:
            try:
                await self._send(member.chat_id, self._ask_goal_again(member, rollover.started))
            except Exception as error:  # e.g. a Member who blocked the bot; ask the others
                log.warning(
                    "goal prompt to member %d failed: %s", member.number, type(error).__name__
                )
        return [Reply(texts.rolled_over(rollover.ended, rollover.started, len(members)))]
