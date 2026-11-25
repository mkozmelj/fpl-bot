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
from fplbot.advice.league_table import league_view
from fplbot.advice.rivals import goal_table, opponent_gameweek
from fplbot.clock import UK_ZONE, Clock
from fplbot.delivery import texts
from fplbot.delivery.elite import EliteGaps
from fplbot.delivery.messages import Button, Reply
from fplbot.delivery.rivals import RivalGaps
from fplbot.delivery.timezones import BUTTON_ZONES, resolve_timezone
from fplbot.sources.footballer_search import search
from fplbot.sources.fpl import (
    FplEntry,
    FplError,
    FplFootballer,
    FplLeague,
    FplSource,
    LeagueKind,
    Lookup,
)
from fplbot.store.leagues import LeagueStore, LeagueTable
from fplbot.store.members import Goal, GoalLeague, MemberRecord, MemberStore
from fplbot.store.reference import Deadlines, ReferenceStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import Squad, SquadPick, SquadStore
from fplbot.store.watch_list import Added, WatchListStore

log = logging.getLogger(__name__)

_TEAM_ID = re.compile(r"\d{1,9}")
_ALERT_TIME = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
# Commands a Member still in setup may use.
_SETUP_COMMANDS = ("/start", "/leave")
# Advice commands, paused while a new season waits for the owner's /rollover (ticket 40): they
# would read or store last season's data. Add new advice commands here.
PAUSED_WHILE_NEW_SEASON_WAITS = frozenset({"/squad", "/league", "/rivals", "/gap", "/watch"})
# An ambiguous name offers one button per match, up to this many.
_MAX_WATCH_CHOICES = 8


class Step(StrEnum):
    """The question a chat is waiting on."""

    TEAM_ID = "team_id"
    CONFIRM_TEAM = "confirm_team"
    GOAL = "goal"
    LEAGUE = "league"
    TZ = "tz"
    TZ_TEXT = "tz_text"
    CONFIRM_LEAVE = "confirm_leave"
    WATCH_PICK = "watch_pick"


@dataclass
class ChatState:
    step: Step | None = None
    # Random token of the chat's live keyboard; buttons carry it as "<token>:<choice>".
    keyboard: str | None = None
    # Pending data for the open question.
    team: FplEntry | None = None
    leagues: dict[str, FplLeague] = field(default_factory=dict[str, FplLeague])
    footballers: dict[str, FplFootballer] = field(default_factory=dict[str, FplFootballer])

    def clear(self) -> None:
        self.step = None
        self.keyboard = None
        self.team = None
        self.leagues = {}
        self.footballers = {}


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
# Called after a change that moves scheduled work (alert time, timezone, joining, leaving).
type SettingsChanged = Callable[[], None]
# Called after a Member's Goal is set or changed (during setup too): recomputes Followed leagues.
type GoalChanged = Callable[[], None]
# The new season waiting for the owner's /rollover, if any (ticket 40).
type NewSeasonWaiting = Callable[[], str | None]


class MemberFlow:
    def __init__(
        self,
        *,
        members: MemberStore,
        watch_list: WatchListStore,
        fpl: FplSource,
        clock: Clock,
        reference: ReferenceStore,
        squads: SquadStore,
        leagues: LeagueStore,
        rival_gaps: RivalGaps,
        elite_gaps: EliteGaps,
        on_team_linked: TeamLinked,
        on_settings_changed: SettingsChanged = lambda: None,
        on_goal_changed: GoalChanged = lambda: None,
        new_season_waiting: NewSeasonWaiting = lambda: None,
    ) -> None:
        self._members = members
        self._new_season_waiting = new_season_waiting
        self._watch_list = watch_list
        self._fpl = fpl
        self._clock = clock
        self._reference = reference
        self._squads = squads
        self._on_team_linked = on_team_linked
        self._on_settings_changed = on_settings_changed
        self._leagues = leagues
        self._rival_gaps = rival_gaps
        self._elite_gaps = elite_gaps
        self._on_goal_changed = on_goal_changed
        self._states: dict[int, ChatState] = {}
        self._commands: dict[str, CommandHandler] = {
            "/start": self._start,
            "/help": self._help,
            "/cancel": self._cancel,
            "/settings": self._settings,
            "/squad": self._squad,
            "/league": self._league,
            "/rivals": self._rivals,
            "/gap": self._gap,
            "/goal": self._goal,
            "/tz": self._tz,
            "/time": self._time,
            "/leave": self._leave,
            "/watch": self._watch,
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
            Step.WATCH_PICK: self._on_watch_pick,
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
            elif command in PAUSED_WHILE_NEW_SEASON_WAITS and self._new_season_waiting():
                turn.say(texts.NEW_SEASON_PAUSED)
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

    def ask_goal_again(self, member: MemberRecord, season: str) -> list[Reply]:
        """After a rollover (ticket 40): the Goal question of setup and ``/goal``, opened in the
        Member's chat as if they had sent ``/goal``."""
        turn = self._turn(member)
        turn.state.clear()
        self._ask_goal(turn, texts.reconfirm_goal(season))
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
            self._on_settings_changed()
            log.info("member %d finished setup", member.number)
            turn.say(texts.all_set(member.team_name or "", _summary(member)))
        else:
            turn.say(texts.saved(_summary(member)))

    def _ask_goal(self, turn: Turn, text: str = texts.ASK_GOAL) -> None:
        turn.ask(
            Step.GOAL,
            text,
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
            self._on_goal_changed()
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
            self._on_goal_changed()
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
        self._on_goal_changed()
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
        self._on_settings_changed()
        await self._advance(turn)

    async def _on_tz_text(self, turn: Turn, text: str) -> None:
        zone = resolve_timezone(text)
        if zone is None:
            turn.say(texts.unknown_timezone(text))
            return
        turn.state.step = None
        await self._members.set_timezone(turn.member.chat_id, zone)
        self._on_settings_changed()
        await self._advance(turn)

    async def _on_confirm_leave(self, turn: Turn, choice: str) -> None:
        if choice != "yes":
            turn.say(texts.LEAVE_KEPT)
            return
        log.info("member %d left", turn.member.number)
        await self._members.delete(turn.member.chat_id)
        await self._leagues.forget_unfollowed()
        self._on_settings_changed()
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
        watched = await self._watch_list.footballer_ids(turn.member.chat_id, self._clock.now())
        names: list[str] | None = []
        if watched:
            footballers = await self._footballers()
            names = None if footballers is None else _names(watched, footballers)
        turn.say(f"{_summary(turn.member)}\n{texts.settings_watch_list(names, len(watched))}")

    async def _squad(self, turn: Turn, argument: str) -> None:
        await self._reference.ensure_loaded(self._fpl)
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

    async def _league(self, turn: Turn, argument: str) -> None:
        member = turn.member
        season = season_of(self._clock.now())
        table = goal_table(member, await self._leagues.followed(member.number, season))
        if table is None or member.team_id is None:
            turn.say(texts.LEAGUE_NONE)
            return
        lines = [_league_text(table, member.team_id)]
        deadlines = await self._reference.deadlines(self._clock.now())
        current = opponent_gameweek(deadlines)
        if table.kind == LeagueKind.H2H and current is not None:
            gameweek = current.id
            opponent = await self._leagues.h2h_opponent(
                member.number, season, table.league_id, gameweek
            )
            if opponent is not None:
                lines.append(texts.league_h2h_opponent(gameweek, opponent.team_name))
        turn.say("\n".join(lines))

    async def _rivals(self, turn: Turn, argument: str) -> None:
        turn.say(await self._rival_gaps.reply(turn.member, argument))

    async def _gap(self, turn: Turn, argument: str) -> None:
        turn.say(await self._elite_gaps.reply(turn.member, argument))

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
        self._on_settings_changed()
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

    # --- Watch list ---

    async def _watch(self, turn: Turn, argument: str) -> None:
        action, _, typed = argument.partition(" ")
        action, typed = action.lower(), typed.strip()
        if not argument:
            await self._show_watch_list(turn)
        elif action == "add" and typed:
            await self._watch_add(turn, typed)
        elif action == "remove" and typed:
            await self._watch_remove(turn, typed)
        else:
            turn.say(texts.WATCH_USAGE)

    async def _show_watch_list(self, turn: Turn) -> None:
        watched = await self._watch_list.footballer_ids(turn.member.chat_id, self._clock.now())
        if not watched:
            turn.say(texts.WATCH_EMPTY)
            return
        footballers = await self._footballers()
        if footballers is None:
            turn.say(texts.FPL_UNREACHABLE)
            return
        turn.say(
            texts.watch_list(
                [
                    texts.watch_line(f.web_name, f.club, f.position, f.now_cost)
                    for f in (footballers[i] for i in watched if i in footballers)
                ]
            )
        )

    async def _watch_add(self, turn: Turn, typed: str) -> None:
        footballers = await self._footballers()
        if footballers is None:
            turn.say(texts.FPL_UNREACHABLE)
            return
        matches = search(footballers.values(), typed)
        if not matches:
            turn.say(texts.watch_no_match(typed))
        elif len(matches) == 1:
            await self._add_to_watch_list(turn, matches[0])
        elif len(matches) > _MAX_WATCH_CHOICES:
            turn.say(texts.watch_too_many(len(matches), typed))
        else:
            turn.state.footballers = {str(f.id): f for f in matches}
            turn.ask(
                Step.WATCH_PICK,
                texts.watch_ambiguous(typed),
                [
                    [(key, texts.watch_choice(f.web_name, f.club, f.position))]
                    for key, f in turn.state.footballers.items()
                ],
            )

    async def _on_watch_pick(self, turn: Turn, choice: str) -> None:
        footballer = turn.state.footballers.get(choice)
        turn.state.footballers = {}
        if footballer is None:
            turn.say(texts.STALE_BUTTON)
            return
        await self._add_to_watch_list(turn, footballer)

    async def _add_to_watch_list(self, turn: Turn, footballer: FplFootballer) -> None:
        added = await self._watch_list.add(turn.member.chat_id, footballer.id, self._clock.now())
        if added is Added.ALREADY_THERE:
            turn.say(texts.watch_already(footballer.web_name))
        elif added is Added.FULL:
            turn.say(texts.WATCH_FULL)
        else:
            log.info("member %d added a Footballer to their Watch list", turn.member.number)
            turn.say(
                texts.watch_added(
                    footballer.web_name, footballer.club, footballer.position, footballer.now_cost
                )
            )

    async def _watch_remove(self, turn: Turn, typed: str) -> None:
        now = self._clock.now()
        watched = await self._watch_list.footballer_ids(turn.member.chat_id, now)
        if not watched:
            turn.say(texts.watch_not_there(typed))
            return
        footballers = await self._footballers()
        if footballers is None:
            turn.say(texts.FPL_UNREACHABLE)
            return
        matches = search((footballers[i] for i in watched if i in footballers), typed)
        if not matches:
            turn.say(texts.watch_not_there(typed))
            return
        await self._watch_list.remove(turn.member.chat_id, matches[0].id, now)
        log.info("member %d removed a Footballer from their Watch list", turn.member.number)
        turn.say(texts.watch_removed(matches[0].web_name))

    async def _footballers(self) -> dict[int, FplFootballer] | None:
        """This season's Footballers by id, from ``bootstrap-static``; ``None`` if FPL can't be
        reached or answers something unusable."""
        try:
            reference = await self._fpl.reference()
        except FplError:
            return None
        return {f.id: f for f in reference.footballers}

    async def _unknown_command(self, turn: Turn, argument: str) -> None:
        turn.say(texts.UNKNOWN_COMMAND)


def _league_text(table: LeagueTable, team_id: int) -> str:
    view = league_view(table.rows, team_id)
    rows: list[str] = []
    for row in view.rows:
        if row.after_gap:
            rows.append(texts.LEAGUE_SKIPPED_ROWS)
        rows.append(texts.league_row(row.rank, row.movement, row.team_name, row.points, row.you))
    notes: list[str] = []
    if not table.complete:
        notes.append(texts.LEAGUE_BIG)
    if not view.you_in_table:
        notes.append(texts.LEAGUE_NOT_IN_TABLE)
    else:
        if view.behind:
            notes.append(texts.league_behind(view.behind.points, view.behind.team_name))
        if view.ahead:
            notes.append(texts.league_ahead(view.ahead.points, view.ahead.team_name))
        leader = view.leader_gap
        notes.append(texts.LEAGUE_LEADER_YOU if leader is None else texts.league_leader(leader))
    header = texts.league_header(table.name, table.gameweek, table.gameweek_finished)
    return "\n".join([header, *rows, "", *notes])


def _summary(member: MemberRecord) -> str:
    if member.goal is Goal.LEAGUE and member.league is not None:
        goal = texts.goal_league(member.league.name)
    else:
        goal = texts.GOAL_OVERALL
    return texts.summary(
        team=texts.team_with_id(member.team_name, member.team_id),
        goal=goal,
        timezone=member.timezone or texts.TIMEZONE_NOT_SET,
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
    zone = ZoneInfo(timezone) if timezone else UK_ZONE
    local = deadlines.next.deadline.astimezone(zone).strftime("%a %d %b %H:%M")
    return texts.picks_hidden(deadlines.next.id, local, deadlines.last.id)


def _names(ids: Sequence[int], footballers: dict[int, FplFootballer]) -> list[str]:
    return [footballers[i].web_name for i in ids if i in footballers]


def _manager(entry: FplEntry) -> str:
    """ "Alex K." style: enough to recognise yourself, without echoing a full name."""
    initial = f" {entry.manager_last_name[0]}." if entry.manager_last_name else ""
    return f"{entry.manager_first_name}{initial}".strip() or texts.UNNAMED_MANAGER


def _hhmm(moment: time | datetime) -> str:
    return moment.strftime("%H:%M")
