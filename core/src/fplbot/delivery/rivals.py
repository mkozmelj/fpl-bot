"""``/rivals`` (ticket 33): the Rival gap, on demand only (nothing is ever pushed).

Reads what the jobs stored: the Member's Squad at the last deadline (older if that one isn't in
yet), the Goal league's table (``advice.rivals.goal_table``), the Rivals' Squads at the same
deadline and average points over the last 4 finished Gameweeks as the weight. Rival selection
and the Gap are pure (``advice/rivals.py``, ``advice/gap.py``); this module renders them in the
shape of ``rivalMessage`` in the Gap prototype. A head-to-head Goal league compares with the
opponent alone (this Gameweek's, i.e. the next deadline's; ``/rivals all``: the whole league).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from fplbot.advice.gap import Backing, Gap, GapLine, gap, shares_of
from fplbot.advice.rivals import all_rivals, goal_table, nearest_rivals
from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.store.footballer_stats import FootballerStatsStore
from fplbot.store.leagues import LeagueStore, LeagueTable
from fplbot.store.members import MemberRecord
from fplbot.store.reference import Deadlines, ReferenceStore
from fplbot.store.rivals import RivalPicksStore, TeamPicks
from fplbot.store.seasons import season_of
from fplbot.store.squads import Squad, SquadStore

# A captain share below this is not worth a mention on a line (prototype).
CAPTAIN_WORTH_MENTIONING = 0.05


class RivalGaps:
    def __init__(
        self,
        *,
        clock: Clock,
        reference: ReferenceStore,
        squads: SquadStore,
        leagues: LeagueStore,
        rivals: RivalPicksStore,
        stats: FootballerStatsStore,
    ) -> None:
        self._clock = clock
        self._reference = reference
        self._squads = squads
        self._leagues = leagues
        self._rivals = rivals
        self._stats = stats

    async def reply(self, member: MemberRecord, argument: str) -> str:
        everyone = argument.strip().lower()
        if everyone not in ("", "all"):
            return texts.RIVALS_USAGE
        now = self._clock.now()
        season = season_of(now)
        deadlines = await self._reference.deadlines(now)
        if deadlines.last is None:
            return texts.NO_DEADLINE_YET
        squad = await self._squads.latest_squad(member.number, season, deadlines.last.id)
        if squad is None:
            return texts.rivals_no_squad(deadlines.last.id)
        table = goal_table(member, await self._leagues.followed(member.number, season))
        if table is None or member.team_id is None:
            return texts.RIVALS_NO_LEAGUE
        context = _Context(season, squad, deadlines)
        if table.kind == "h2h" and not everyone:
            return await self._against_opponent(member, table, context)
        rows = (
            all_rivals(table.rows, member.team_id)
            if everyone
            else nearest_rivals(table.rows, member.team_id)
        )
        if rows is None:
            return texts.RIVALS_NOT_IN_TABLE
        picks = await self._rivals.team_picks(season, squad.gameweek, [r.entry_id for r in rows])
        rivals = [picks[r.entry_id] for r in rows if r.entry_id in picks]
        if not rivals:
            return texts.rivals_no_picks(squad.gameweek)
        weights = await self._stats.average_points(season)
        if not weights:
            return texts.RIVALS_NO_STATS
        you = _backing(squad)
        result = gap(you, shares_of(_backing_of(p) for p in rivals), weights)
        names = await self._names(season, result, [you.captain])
        same = sum(1 for p in rivals if you.captain is not None and p.captain == you.captain)
        lines = [
            texts.rivals_header(table.name, len(rivals), bool(everyone)),
            *_as_of(context),
            *_blocks(result, names, texts.RIVALS_YOU_BACK),
            "",
            texts.rivals_captain(_name(names, you.captain), same, len(rivals)),
        ]
        if result.empty:
            lines.append(texts.RIVALS_NOTHING_STANDS_OUT)
        return "\n".join(lines)

    async def _against_opponent(
        self, member: MemberRecord, table: LeagueTable, context: _Context
    ) -> str:
        deadlines = context.deadlines
        current = deadlines.next or deadlines.last
        if current is None:
            return texts.NO_DEADLINE_YET
        opponent = await self._leagues.h2h_opponent(
            member.number, context.season, table.league_id, current.id
        )
        if opponent is None:
            return texts.rivals_no_opponent(current.id)
        if opponent.entry_id is None:
            return texts.rivals_bye(current.id)
        gameweek = context.squad.gameweek
        picks = (await self._rivals.team_picks(context.season, gameweek, [opponent.entry_id])).get(
            opponent.entry_id
        )
        if picks is None:
            return texts.rivals_no_picks(gameweek)
        weights = await self._stats.average_points(context.season)
        if not weights:
            return texts.RIVALS_NO_STATS
        you, they = _backing(context.squad), _backing_of(picks)
        result = gap(you, shares_of([they]), weights)
        names = await self._names(context.season, result, [you.captain, they.captain])
        lines = [
            texts.rivals_opponent_header(table.name, current.id, opponent.team_name),
            *_as_of(context),
            *_blocks(result, names, texts.RIVALS_OPPONENT_YOU_BACK),
            "",
            texts.rivals_opponent_captain(
                _name(names, you.captain), _name(names, they.captain), you.captain == they.captain
            ),
        ]
        if result.empty:
            lines.append(texts.RIVALS_OPPONENT_NOTHING_STANDS_OUT)
        return "\n".join(lines)

    async def _names(
        self, season: str, result: Gap, captains: Sequence[int | None]
    ) -> dict[int, str]:
        ids = {line.footballer_id for line in (*result.you_back, *result.they_back)}
        ids.update(c for c in captains if c is not None)
        return await self._reference.footballer_names(season, ids)


@dataclass(frozen=True)
class _Context:
    season: str
    squad: Squad  # the Member's Squad compared; Rivals' picks are read at its Gameweek
    deadlines: Deadlines


def _backing(squad: Squad) -> Backing:
    captain = next((p.footballer_id for p in squad.xi + squad.bench if p.is_captain), None)
    return Backing(frozenset(p.footballer_id for p in squad.xi), captain)


def _backing_of(picks: TeamPicks) -> Backing:
    return Backing(picks.xi, picks.captain)


def _as_of(context: _Context) -> list[str]:
    """Between deadlines: the Squads are the last deadline's, and newer picks are hidden."""
    upcoming = context.deadlines.next
    lines = [texts.rivals_squad_as_of(context.squad.gameweek, upcoming.id if upcoming else None)]
    if upcoming is not None:
        lines.append(texts.RIVALS_PICKS_AS_OF_LAST_DEADLINE)
    return lines


def _blocks(result: Gap, names: dict[int, str], you_back_title: str) -> list[str]:
    lines: list[str] = []
    for title, side in (
        (you_back_title, result.you_back),
        (texts.RIVALS_THEY_BACK, result.they_back),
    ):
        if side:
            lines += ["", title, *(_line(line, names) for line in side)]
    return lines


def _line(line: GapLine, names: dict[int, str]) -> str:
    captain = None
    if line.you_captain or line.reference.captain >= CAPTAIN_WORTH_MENTIONING:
        captain = (line.you_captain, _percent(line.reference.captain))
    return texts.rivals_line(
        _name(names, line.footballer_id),
        line.you_start,
        _percent(line.reference.xi),
        captain,
        _signed(line.edge),
    )


def _name(names: dict[int, str], footballer: int | None) -> str:
    if footballer is None:
        return "nobody"
    return names.get(footballer, f"Footballer {footballer}")


def _percent(share: float) -> int:
    return int(Decimal(str(share * 100)).quantize(Decimal(1), ROUND_HALF_UP))


def _signed(edge: float) -> str:
    """``+4.0`` / ``−3.5`` (a true minus sign, as in the prototype), half rounded up."""
    size = Decimal(str(abs(edge))).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return f"{'+' if edge >= 0 else '−'}{size}"
