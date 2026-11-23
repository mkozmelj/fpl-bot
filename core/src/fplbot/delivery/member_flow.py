"""The conversation with allow-listed Members: setup, settings and ``/leave`` (ticket 28).

The state machine follows the pure bot module of the ticket 14 prototype:

- Setup asks for whatever is still missing, in order: team ID, Goal (and, for Mini-league, the
  league), timezone. When nothing is missing a joining Member becomes active.
- Each chat has at most one open question (``Step``) and one live keyboard. Any ``/command``
  clears both. A joining Member who sends a command other than ``/start`` or ``/leave`` is
  re-asked the open setup question.
- A button press counts only if it comes from the chat's latest keyboard, and only once.
  Anything else is answered with ``STALE_BUTTON`` and changes nothing.

Open questions live in memory only: a restart forgets them (old buttons then read as stale,
and ``/start`` resumes setup from what is stored).

Adding to the conversation (later tickets): register a command in ``_commands``; for a question
answered by text register a ``Step`` in ``_text_steps``, for one answered by buttons in
``_button_steps``; ask it with ``turn.ask(step, text, rows_of_(choice, label))``. Keep data
needed to resolve a choice on ``ChatState`` (see ``leagues``).
"""

import logging
import re
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from fplbot.advice.alert_time import price_alert_send_time
from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.messages import Button, Reply
from fplbot.delivery.timezones import BUTTON_ZONES, resolve_timezone
from fplbot.sources.fpl import FplEntry, FplLeague, FplSource, Lookup
from fplbot.store.members import Goal, GoalLeague, MemberRecord, MemberStore
from fplbot.store.reference import Deadlines, ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import Squad, SquadPick, SquadStore

log = logging.getLogger(__name__)

_TEAM_ID = re.compile(r"\d{1,9}")
_ALERT_TIME = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
# Commands a Member still in setup may use.
_SETUP_COMMANDS = ("/start", "/leave")


class Step(StrEnum):
    """The question a chat is waiting on."""

    TEAM_ID = "team_id"
    CONFIRM_TEAM = "confirm_team"
    GOAL = "goal"
    LEAGUE = "league"
    TZ = "tz"
    TZ_TEXT = "tz_text"
    CONFIRM_LEAVE = "confirm_leave"


@dataclass
class ChatState:
    step: Step | None = None
    # Random token of the chat's live keyboard; buttons carry it as "<token>:<choice>".
    keyboard: str | None = None
    # Pending data for the open question.
    team: FplEntry | None = None
    leagues: dict[str, FplLeague] = field(default_factory=dict[str, FplLeague])

    def clear(self) -> None:
        self.step = None
        self.keyboard = None
        self.team = None
        self.leagues = {}


@dataclass
class Turn:
    """One update's worth of conversation with one Member."""

    member: MemberRecord
    state: ChatState
    replies: list[Reply] = field(default_factory=list[Reply])

    def say(self, text: str) -> None:
        self.replies.append(Reply(text))

    def ask(self, step: Step, text: str, buttons: Sequence[Sequence[tuple[str, str]]] = ()) -> None:
        """Send ``text`` and wait for ``step``. ``buttons`` are rows of ``(choice, label)``;
        a new keyboard makes every earlier one stale."""
        self.state.step = step
        self.state.keyboard = secrets.token_hex(4) if buttons else None
        keyboard = tuple(
            tuple(Button(label, f"{self.state.keyboard}:{choice}") for choice, label in row)
            for row in buttons
        )
        self.replies.append(Reply(text, keyboard))


type CommandHandler = Callable[[Turn, str], Awaitable[None]]
type StepHandler = Callable[[Turn, str], Awaitable[None]]
# Called with (Member number, team ID) once a Member has linked their team: starts the backfill.
type TeamLinked = Callable[[int, int], None]


class MemberFlow:
    def __init__(
        self,
        *,
        members: MemberStore,
        fpl: FplSource,
        clock: Clock,
        reference: ReferenceStore,
        squads: SquadStore,
        on_team_linked: TeamLinked,
    ) -> None:
        self._members = members
        self._fpl = fpl
        self._clock = clock
        self._reference = reference
        self._squads = squads
        self._on_team_linked = on_team_linked
        self._states: dict[int, ChatState] = {}
        self._commands: dict[str, CommandHandler] = {
            "/start": self._start,
            "/help": self._help,
            "/cancel": self._cancel,
            "/settings": self._settings,
            "/squad": self._squad,
            "/goal": self._goal,
            "/tz": self._tz,
            "/time": self._time,
            "/leave": self._leave,
        }
        self._text_steps: dict[Step, StepHandler] = {
            Step.TEAM_ID: self._on_team_id,
            Step.TZ_TEXT: self._on_tz_text,
        }
        self._button_steps: dict[Step, StepHandler] = {
            Step.CONFIRM_TEAM: self._on_confirm_team,
            Step.GOAL: self._on_goal,
            Step.LEAGUE: self._on_league,
            Step.TZ: self._on_tz,
            Step.CONFIRM_LEAVE: self._on_confirm_leave,
        }

    async def begin(self, member: MemberRecord) -> list[Reply]:
        """Start setup for a Member who has just redeemed an invite."""
        turn = self._turn(member)
        await self._advance(turn)
        return turn.replies

    async def on_text(self, member: MemberRecord, command: str | None, text: str) -> list[Reply]:
        """``command`` is the lower-cased ``/command`` (``text`` then holds its argument), or
        ``None`` for plain text."""
        turn = self._turn(member)
        if command is not None:
            turn.state.clear()
            if member.joining and command not in _SETUP_COMMANDS:
                turn.say(texts.FINISH_SETUP_FIRST)
                await self._advance(turn)
            else:
                await self._commands.get(command, self._unknown_command)(turn, text)
            return turn.replies

        step = turn.state.step
        if step is None and member.joining and member.team_id is None:
            step = Step.TEAM_ID  # e.g. after a restart: setup always starts with the team ID
        handler = self._text_steps.get(step) if step else None
        if handler is not None:
            await handler(turn, text)
        elif step is None and member.joining:
            await self._advance(turn)
        else:
            turn.say(texts.NOT_UNDERSTOOD)
        return turn.replies

    async def on_press(self, member: MemberRecord, data: str) -> list[Reply]:
        turn = self._turn(member)
        state = turn.state
        token, _, choice = data.partition(":")
        handler = self._button_steps.get(state.step) if state.step else None
        if handler is None or state.keyboard is None or token != state.keyboard:
            log.info("member %d tapped an out-of-date button", member.number)
            return [Reply(texts.STALE_BUTTON)]
        state.step = None
        state.keyboard = None
        await handler(turn, choice)
        return turn.replies

    def forget(self, chat_id: int) -> None:
        self._states.pop(chat_id, None)

    def _turn(self, member: MemberRecord) -> Turn:
        return Turn(member, self._states.setdefault(member.chat_id, ChatState()))

    # --- setup chain: ask for whatever is still missing ---

    async def _advance(self, turn: Turn) -> None:
        member = await self._members.get(turn.member.chat_id)
        if member is None:
            return
        turn.member = member
        if member.team_id is None:
            turn.ask(Step.TEAM_ID, texts.ASK_TEAM_ID)
        elif member.goal is None:
            self._ask_goal(turn)
        elif member.timezone is None:
            self._ask_tz(turn)
        elif member.joining:
            await self._members.activate(member.chat_id)
            log.info("member %d finished setup", member.number)
            turn.say(texts.all_set(member.team_name or "", _summary(member)))
        else:
            turn.say(texts.saved(_summary(member)))

    def _ask_goal(self, turn: Turn) -> None:
        turn.ask(
            Step.GOAL,
            texts.ASK_GOAL,
            [[("overall", texts.GOAL_OVERALL), ("league", texts.GOAL_LEAGUE)]],
        )

    def _ask_tz(self, turn: Turn) -> None:
        zones = [(f"tz:{zone}", zone) for zone in BUTTON_ZONES]
        turn.ask(
            Step.TZ,
            texts.ask_tz(_hhmm(turn.member.alert_time)),
            [zones[:2], zones[2:], [("other", texts.TZ_OTHER)]],
        )

    async def _on_team_id(self, turn: Turn, text: str) -> None:
        if not _TEAM_ID.fullmatch(text):
            turn.say(texts.NOT_A_TEAM_ID)
            return
        team_id = int(text)
        if await self._members.team_linked_elsewhere(team_id, turn.member.chat_id):
            log.info("member %d tried a team linked to another member", turn.member.number)
            turn.say(texts.TEAM_TAKEN)
            return
        entry = await self._fpl.entry(team_id)
        if entry is Lookup.NOT_FOUND:
            turn.say(texts.unknown_team(text))
        elif isinstance(entry, Lookup):
            turn.say(texts.FPL_UNREACHABLE)
        else:
            turn.state.team = entry
            turn.ask(
                Step.CONFIRM_TEAM,
                texts.confirm_team(entry.team_name, _manager(entry), entry.overall_rank),
                [[("yes", texts.CONFIRM_YES), ("no", texts.CONFIRM_NO)]],
            )

    async def _on_confirm_team(self, turn: Turn, choice: str) -> None:
        team, turn.state.team = turn.state.team, None
        if choice != "yes" or team is None:
            turn.ask(Step.TEAM_ID, texts.WRONG_TEAM)
            return
        if not await self._members.link_team(turn.member.chat_id, team.id, team.team_name):
            turn.say(texts.TEAM_TAKEN)
            turn.state.step = Step.TEAM_ID
            return
        log.info("member %d linked a team", turn.member.number)
        self._on_team_linked(turn.member.number, team.id)
        await self._advance(turn)

    async def _on_goal(self, turn: Turn, choice: str) -> None:
        if choice == "overall":
            await self._members.set_goal(turn.member.chat_id, Goal.OVERALL, None)
            await self._advance(turn)
            return
        if choice != "league":
            turn.say(texts.STALE_BUTTON)
            return
        team_id = turn.member.team_id
        entry = await self._fpl.entry(team_id) if team_id is not None else Lookup.NOT_FOUND
        if isinstance(entry, Lookup):
            turn.say(texts.FPL_UNREACHABLE)
            return
        if not entry.mini_leagues:
            await self._members.set_goal(turn.member.chat_id, Goal.OVERALL, None)
            turn.say(texts.NO_MINI_LEAGUE)
            await self._advance(turn)
            return
        turn.state.leagues = {f"{league.kind}:{league.id}": league for league in entry.mini_leagues}
        turn.ask(
            Step.LEAGUE,
            texts.ASK_LEAGUE,
            [[(key, league.name)] for key, league in turn.state.leagues.items()],
        )

    async def _on_league(self, turn: Turn, choice: str) -> None:
        league = turn.state.leagues.get(choice)
        turn.state.leagues = {}
        if league is None:
            turn.say(texts.STALE_BUTTON)
            return
        await self._members.set_goal(
            turn.member.chat_id, Goal.LEAGUE, GoalLeague(league.id, league.kind, league.name)
        )
        await self._advance(turn)

    async def _on_tz(self, turn: Turn, choice: str) -> None:
        if choice == "other":
            turn.ask(Step.TZ_TEXT, texts.ASK_TZ_TEXT)
            return
        zone = choice.removeprefix("tz:")
        if zone not in BUTTON_ZONES:
            turn.say(texts.STALE_BUTTON)
            return
        await self._members.set_timezone(turn.member.chat_id, zone)
        await self._advance(turn)

    async def _on_tz_text(self, turn: Turn, text: str) -> None:
        zone = resolve_timezone(text)
        if zone is None:
            turn.say(texts.unknown_timezone(text))
            return
        turn.state.step = None
        await self._members.set_timezone(turn.member.chat_id, zone)
        await self._advance(turn)

    async def _on_confirm_leave(self, turn: Turn, choice: str) -> None:
        if choice != "yes":
            turn.say(texts.LEAVE_KEPT)
            return
        log.info("member %d left", turn.member.number)
        await self._members.delete(turn.member.chat_id)
        self.forget(turn.member.chat_id)
        turn.say(texts.LEFT)

    # --- commands ---

    async def _start(self, turn: Turn, argument: str) -> None:
        if turn.member.joining:
            await self._advance(turn)
        else:
            turn.say(texts.welcome_back(turn.member.team_name or ""))

    async def _help(self, turn: Turn, argument: str) -> None:
        turn.say(texts.help_text())

    async def _cancel(self, turn: Turn, argument: str) -> None:
        turn.say(texts.CANCELLED)

    async def _settings(self, turn: Turn, argument: str) -> None:
        turn.say(_summary(turn.member))

    async def _squad(self, turn: Turn, argument: str) -> None:
        await self._reference.refresh_if_stale(self._fpl)  # fail-soft: else use what's stored
        now = self._clock.now()
        deadlines = await self._reference.deadlines(now)
        last = deadlines.last
        if last is None:
            turn.say(texts.NO_DEADLINE_YET if deadlines.next else texts.FPL_UNREACHABLE)
            return
        hidden = _picks_hidden_note(deadlines, turn.member.timezone)
        squad = await self._squads.squad(turn.member.number, season_of(now), last.id)
        if squad is None:
            turn.say(texts.no_squad(last.id, hidden))
            return
        turn.say(_squad_text(turn.member.team_name or "", squad, hidden))

    async def _goal(self, turn: Turn, argument: str) -> None:
        self._ask_goal(turn)

    async def _tz(self, turn: Turn, argument: str) -> None:
        self._ask_tz(turn)

    async def _time(self, turn: Turn, argument: str) -> None:
        match = _ALERT_TIME.fullmatch(argument)
        if match is None or turn.member.timezone is None:
            turn.say(texts.TIME_FORMAT)
            return
        chosen = time(int(match[1]), int(match[2]))
        await self._members.set_alert_time(turn.member.chat_id, chosen)
        zone_name = turn.member.timezone
        zone = ZoneInfo(zone_name)
        send = price_alert_send_time(chosen, zone, self._clock.now().astimezone(zone).date())
        if send.clamped:
            turn.say(
                texts.alert_time_clamped(
                    _hhmm(chosen), zone_name, _hhmm(send.at), _hhmm(send.at.astimezone(zone))
                )
            )
        else:
            turn.say(texts.alert_time_set(_hhmm(chosen), zone_name))

    async def _leave(self, turn: Turn, argument: str) -> None:
        turn.ask(
            Step.CONFIRM_LEAVE,
            texts.ASK_LEAVE,
            [[("yes", texts.LEAVE_YES), ("no", texts.LEAVE_NO)]],
        )

    async def _unknown_command(self, turn: Turn, argument: str) -> None:
        turn.say(texts.UNKNOWN_COMMAND)


def _summary(member: MemberRecord) -> str:
    if member.goal is Goal.LEAGUE and member.league is not None:
        goal = texts.goal_league(member.league.name)
    else:
        goal = texts.GOAL_OVERALL
    return texts.summary(
        team=f"{member.team_name} (ID {member.team_id})",
        goal=goal,
        timezone=member.timezone or "not set",
        alert_time=_hhmm(member.alert_time),
    )


_POSITION_ORDER = ("GKP", "DEF", "MID", "FWD")


def _squad_text(team_name: str, squad: Squad, hidden_note: str | None) -> str:
    # "?": a Footballer missing from reference data (e.g. added after the last refresh).
    lines = [
        (position, [_pick_label(p) for p in squad.xi if (p.position or "?") == position])
        for position in (*_POSITION_ORDER, "?")
    ]
    return texts.squad(
        team_name,
        squad.gameweek,
        [(position, names) for position, names in lines if names],
        [_pick_label(p) for p in squad.bench],
        hidden_note,
    )


def _pick_label(pick: SquadPick) -> str:
    if pick.is_captain:
        return texts.captain(pick.name)
    if pick.is_vice_captain:
        return texts.vice_captain(pick.name)
    return pick.name


def _picks_hidden_note(deadlines: Deadlines, timezone: str | None) -> str | None:
    """Between deadlines: which Gameweek's picks FPL still hides, and until when."""
    if deadlines.next is None or deadlines.last is None:
        return None
    zone = ZoneInfo(timezone or "Europe/London")
    local = deadlines.next.deadline.astimezone(zone).strftime("%a %d %b %H:%M")
    return texts.picks_hidden(deadlines.next.id, local, deadlines.last.id)


def _manager(entry: FplEntry) -> str:
    """ "Alex K." style: enough to recognise yourself, without echoing a full name."""
    initial = f" {entry.manager_last_name[0]}." if entry.manager_last_name else ""
    return f"{entry.manager_first_name}{initial}".strip() or "an unnamed manager"


def _hhmm(moment: time | datetime) -> str:
    return moment.strftime("%H:%M")
