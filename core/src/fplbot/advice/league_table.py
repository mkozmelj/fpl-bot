"""The league progress view (``/league``, ticket 32): pure decisions over a stored table.

Follows ``leagueMessage`` in the Gap prototype: each row's rank movement since the last update,
points behind the Rival directly above, ahead of the Rival directly below, and the gap to the
leader. A Member at the top or bottom gets only the lines that apply.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from fplbot.sources.fpl import FplStanding


@dataclass(frozen=True)
class ViewRow:
    rank: int
    movement: int  # places gained since the last update (negative: lost); 0 if unknown
    team_name: str
    points: int
    you: bool
    after_gap: bool  # rows were left out just before this one (a big league's followed subset)


@dataclass(frozen=True)
class PointsGap:
    points: int
    team_name: str


@dataclass(frozen=True)
class LeagueView:
    rows: tuple[ViewRow, ...]
    you_in_table: bool
    behind: PointsGap | None  # the Rival directly above you
    ahead: PointsGap | None  # the Rival directly below you
    # Points the leader is ahead of you; None when you lead (or are not in the table).
    leader_gap: int | None


def league_view(rows: Sequence[FplStanding], your_entry: int) -> LeagueView:
    """``rows`` in FPL's order (positions may skip); ``your_entry`` the Member's FPL team."""
    view_rows = tuple(
        ViewRow(
            rank=row.rank,
            movement=row.last_rank - row.rank if row.last_rank else 0,
            team_name=row.team_name,
            points=row.points,
            you=row.entry_id == your_entry,
            after_gap=index > 0 and row.position != rows[index - 1].position + 1,
        )
        for index, row in enumerate(rows)
    )
    mine = next((i for i, row in enumerate(rows) if row.entry_id == your_entry), None)
    if mine is None:
        return LeagueView(view_rows, False, None, None, None)
    you = rows[mine]
    above = rows[mine - 1] if mine > 0 and rows[mine - 1].position == you.position - 1 else None
    below = rows[mine + 1] if mine + 1 < len(rows) else None
    if below is not None and below.position != you.position + 1:
        below = None
    leader = rows[0] if rows[0].position == 1 else None
    return LeagueView(
        rows=view_rows,
        you_in_table=True,
        behind=PointsGap(above.points - you.points, above.team_name) if above else None,
        ahead=PointsGap(you.points - below.points, below.team_name) if below else None,
        leader_gap=leader.points - you.points if leader and leader is not you else None,
    )
