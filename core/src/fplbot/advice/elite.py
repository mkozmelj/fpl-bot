"""Elite sample statistics (ticket 34): pure, plain data in and out.

A share (XI share, captain share, ownership) estimated from a simple random sample of ``n``
managers out of a cohort of ``N`` has a 95% margin of error of

    1.96 * sqrt(p(1 - p) / n) * sqrt((N - n) / (N - 1))

(finite-population correction). We quote the worst case, p = 0.5, for every Footballer; most
shares are tighter. ``sample_size_for`` inverts it: the sample a target margin needs (research
03: 1,937 for the top 10k at ±2%).

The top 100k (ticket 35) is estimated from two strata (research 03's stratified design): the
top-10k sample, and a sample of ranks 10,001-100,000. Each share is the strata's shares
weighted by stratum size (0.1 and 0.9); its margin of error is 1.96 * sqrt(sum of W_h^2 *
0.25 / n_h * correction_h). With one stratum this is the plain formula above, so ``figures``
serves both cohorts.
"""

import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fplbot.sources.fpl import FplPicks
from fplbot.store.elite import EliteFigures, FootballerShares

Z_95 = 1.96
XI_SLOTS = 11


def margin_of_error(sample_size: int, cohort_size: int) -> float:
    """Worst-case 95% margin of error of a share, as a share (0.02 is ±2%)."""
    if sample_size <= 0:
        return 1.0
    return Z_95 * math.sqrt(_variance(sample_size, cohort_size))


def _variance(sample_size: int, size: int) -> float:
    """Worst-case variance of a share from a simple random sample of ``size`` managers."""
    if size <= 1 or sample_size >= size:
        return 0.0
    return 0.25 / sample_size * (size - sample_size) / (size - 1)


def sample_size_for(cohort_size: int, margin: float) -> int:
    """The smallest sample whose worst-case 95% margin of error is at most ``margin``."""
    infinite = Z_95**2 * 0.25 / margin**2
    return min(cohort_size, math.ceil(infinite / (1 + (infinite - 1) / cohort_size)))


@dataclass
class EliteTally:
    """Counts over the Squads sampled so far. Holds no manager's ID and keeps no Squad: each
    one only bumps the counters."""

    size: int = 0
    owned: Counter[int] = field(default_factory=Counter[int])
    started: Counter[int] = field(default_factory=Counter[int])
    captained: Counter[int] = field(default_factory=Counter[int])
    multipliers: Counter[int] = field(default_factory=Counter[int])
    chips: Counter[str] = field(default_factory=Counter[str])

    def add(self, squad: FplPicks) -> None:
        self.size += 1
        for pick in squad.picks:
            self.owned[pick.footballer_id] += 1
            self.multipliers[pick.footballer_id] += pick.multiplier
            if pick.slot <= XI_SLOTS:
                self.started[pick.footballer_id] += 1
            if pick.is_captain:
                self.captained[pick.footballer_id] += 1
        if squad.active_chip:
            self.chips[squad.active_chip] += 1


@dataclass(frozen=True)
class Stratum:
    """One stratum's sample: ``size`` managers, ``target`` of them aimed for, ``tally`` read."""

    tally: EliteTally
    size: int
    target: int


def figures(
    cohort: str,
    gameweek: int,
    strata: Sequence[Stratum],
    *,
    partial: bool = False,
    read_late: bool = False,
) -> EliteFigures:
    """A cohort's figures from its strata's samples (one stratum: a simple random sample).
    Every stratum must have read at least one Squad."""
    total = sum(stratum.size for stratum in strata)
    weights = [stratum.size / total for stratum in strata]
    footballers = {f for stratum in strata for f in stratum.tally.owned}
    chips = {c for stratum in strata for c in stratum.tally.chips}

    def share[K](counts: Callable[[EliteTally], Counter[K]], key: K) -> float:
        return sum(
            w * counts(s.tally)[key] / s.tally.size for w, s in zip(weights, strata, strict=True)
        )

    variance = sum(
        w * w * _variance(s.tally.size, s.size) for w, s in zip(weights, strata, strict=True)
    )
    return EliteFigures(
        cohort=cohort,
        gameweek=gameweek,
        cohort_size=total,
        target_size=sum(stratum.target for stratum in strata),
        sample_size=sum(stratum.tally.size for stratum in strata),
        margin_of_error=Z_95 * math.sqrt(variance),
        footballers={
            f: FootballerShares(
                ownership=share(lambda t: t.owned, f),
                xi=share(lambda t: t.started, f),
                captain=share(lambda t: t.captained, f),
                eo=share(lambda t: t.multipliers, f),
            )
            for f in footballers
        },
        chips={c: share(lambda t: t.chips, c) for c in chips},
        partial=partial,
        read_late=read_late,
    )
