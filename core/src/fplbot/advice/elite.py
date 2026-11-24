"""Elite sample statistics (ticket 34): pure, plain data in and out.

A share (XI share, captain share, ownership) estimated from a simple random sample of ``n``
managers out of a cohort of ``N`` has a 95% margin of error of

    1.96 * sqrt(p(1 - p) / n) * sqrt((N - n) / (N - 1))

(finite-population correction). We quote the worst case, p = 0.5, for every Footballer; most
shares are tighter. ``sample_size_for`` inverts it: the sample a target margin needs (research
03: 1,937 for the top 10k at ±2%).
"""

import math
from collections import Counter
from dataclasses import dataclass, field

from fplbot.sources.fpl import FplPicks
from fplbot.store.elite import EliteFigures, FootballerShares

Z_95 = 1.96
XI_SLOTS = 11


def margin_of_error(sample_size: int, cohort_size: int) -> float:
    """Worst-case 95% margin of error of a share, as a share (0.02 is ±2%)."""
    if sample_size <= 0:
        return 1.0
    if cohort_size <= 1 or sample_size >= cohort_size:
        return 0.0
    correction = (cohort_size - sample_size) / (cohort_size - 1)
    return Z_95 * math.sqrt(0.25 / sample_size * correction)


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

    def figures(
        self, cohort: str, gameweek: int, *, cohort_size: int, target_size: int
    ) -> EliteFigures:
        n = self.size
        return EliteFigures(
            cohort=cohort,
            gameweek=gameweek,
            cohort_size=cohort_size,
            target_size=target_size,
            sample_size=n,
            margin_of_error=margin_of_error(n, cohort_size),
            footballers={
                footballer: FootballerShares(
                    ownership=self.owned[footballer] / n,
                    xi=self.started[footballer] / n,
                    captain=self.captained[footballer] / n,
                    eo=self.multipliers[footballer] / n,
                )
                for footballer in self.owned
            },
            chips={chip: count / n for chip, count in self.chips.items()},
        )
