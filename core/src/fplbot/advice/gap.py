"""The Gap (spec, Gap views; ``computeGap`` in the Gap prototype): pure, plain data in and out.

For each Footballer, against a reference group (Rivals, or an Elite cohort):

    edge(f) = (you start − ref XI share) * w(f) + (you captain − ref captain share) * w(f)

in points per Gameweek you gain (+) or give up (−) against the reference group's average. The
weight ``w`` is an input: Phase 1 passes average points over the last 4 finished Gameweeks,
Phase 2 can pass Expected points without changing anything here.

A Footballer is shown only when his difference beats twice the margin of error (the XI-share
difference; the captain-share difference for the captain-only view) and ``|edge| >= 0.35``: at
most 3 a side, biggest first. For Rivals the margin of error is 0 (their picks are known, not
sampled). There is deliberately no summed "net" edge: the Footballer pool is incomplete.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MIN_EDGE = 0.35  # points a Gameweek
PER_SIDE = 3


@dataclass(frozen=True)
class Backing:
    """Who a Squad starts and captains."""

    xi: frozenset[int]
    captain: int | None


@dataclass(frozen=True)
class Shares:
    """How much of the reference group starts (``xi``) and captains a Footballer, 0 to 1."""

    xi: float
    captain: float


@dataclass(frozen=True)
class GapLine:
    footballer_id: int
    you_start: bool
    you_captain: bool
    reference: Shares
    weight: float
    edge: float  # points per Gameweek against the reference group


@dataclass(frozen=True)
class Gap:
    you_back: tuple[GapLine, ...]  # edge > 0: you back him, the reference mostly doesn't
    they_back: tuple[GapLine, ...]  # edge < 0: the reference backs him, you don't

    @property
    def empty(self) -> bool:
        return not self.you_back and not self.they_back


def shares_of(group: Iterable[Backing]) -> dict[int, Shares]:
    """Reference shares from a group of known Squads (Rivals): each counts equally."""
    squads = list(group)
    if not squads:
        return {}
    starts = Counter(f for squad in squads for f in squad.xi)
    captains = Counter(squad.captain for squad in squads if squad.captain is not None)
    n = len(squads)
    return {
        f: Shares(xi=starts[f] / n, captain=captains[f] / n) for f in set(starts) | set(captains)
    }


def gap(
    you: Backing,
    reference: Mapping[int, Shares],
    weights: Mapping[int, float],
    *,
    margin_of_error: float = 0.0,
    captain_only: bool = False,
) -> Gap:
    """The Gap of ``you`` against ``reference`` shares. ``weights`` per Footballer (missing:
    0); ``margin_of_error`` as a share (0.02 is ±2%)."""
    none = Shares(0.0, 0.0)
    lines: list[GapLine] = []
    candidates = set(reference) | you.xi
    if you.captain is not None:
        candidates.add(you.captain)
    for footballer in sorted(candidates):
        ref = reference.get(footballer, none)
        starts, captains = footballer in you.xi, footballer == you.captain
        weight = weights.get(footballer, 0.0)
        d_xi, d_captain = float(starts) - ref.xi, float(captains) - ref.captain
        edge = d_captain * weight if captain_only else (d_xi + d_captain) * weight
        difference = abs(d_captain) if captain_only else abs(d_xi)
        if difference > 2 * margin_of_error and abs(edge) >= MIN_EDGE:
            lines.append(GapLine(footballer, starts, captains, ref, weight, edge))
    you_back = sorted((x for x in lines if x.edge > 0), key=lambda x: -x.edge)
    they_back = sorted((x for x in lines if x.edge < 0), key=lambda x: x.edge)
    return Gap(tuple(you_back[:PER_SIDE]), tuple(they_back[:PER_SIDE]))
