"""Rival selection for the Rival gap (spec, Gap views): pure decisions over a stored table.

``/rivals``: the nearest 2 above and 2 below the Member by place in the table (FPL's order;
fewer at the top or bottom). ``/rivals all``: everyone else in the table. A big Goal league's
table is the stored subset (top 10 and the 20 either side of the Member), so "all" means that.
"""

from collections.abc import Sequence

from fplbot.sources.fpl import FplStanding, LeagueKind
from fplbot.store.leagues import LeagueTable
from fplbot.store.members import Goal, MemberRecord
from fplbot.store.reference import Deadlines, GameweekInfo

NEAREST = 2


def goal_table(member: MemberRecord, followed: Sequence[LeagueTable]) -> LeagueTable | None:
    """The Goal league's table; with Overall rank as Goal (story 20), the first classic Followed
    league (in FPL's order of the Member's Mini-leagues), or the first Followed league of any
    kind when none is classic. Used by ``/league`` and ``/rivals``."""
    league = member.league
    if member.goal is Goal.LEAGUE and league is not None:
        return next(
            (t for t in followed if (t.kind, t.league_id) == (league.kind, league.id)), None
        )
    classic = (t for t in followed if t.kind == LeagueKind.CLASSIC)
    return next(classic, followed[0] if followed else None)


def opponent_gameweek(deadlines: Deadlines) -> GameweekInfo | None:
    """The Gameweek whose head-to-head opponent is "my opponent this Gameweek" (story 21), for
    ``/rivals`` and ``/league`` alike: the one being played, i.e. the last deadline's; before the
    season's first deadline, the next one's."""
    return deadlines.last or deadlines.next


def nearest_rivals(rows: Sequence[FplStanding], your_entry: int) -> tuple[FplStanding, ...] | None:
    """The Rivals within ``NEAREST`` places of you; ``None`` when you are not in the table."""
    you = next((row for row in rows if row.entry_id == your_entry), None)
    if you is None:
        return None
    return tuple(
        row
        for row in rows
        if row.entry_id != your_entry and abs(row.position - you.position) <= NEAREST
    )


def all_rivals(rows: Sequence[FplStanding], your_entry: int) -> tuple[FplStanding, ...]:
    return tuple(row for row in rows if row.entry_id != your_entry)
