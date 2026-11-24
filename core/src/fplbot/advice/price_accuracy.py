"""How well FPL's price predictor did (tickets 15, 37): plain data in, the ``/accuracy`` report
out.

Every Footballer's likelihood code (-5..+5) at the night's first Price-alert time is scored
against the actual change from that night's archive (horizon "tonight") and, for the code for
the next night, against the following night's archive ("tomorrow"). A hit: a positive code and
a rise, a negative code and a fall, or 0 and no change.

Floors, judged per code over a rolling 14 nights once the code has at least 20 predictions
there: 70% for +/-4 (Likely) and 85% for +/-5 (Very likely). Below one, the report flags it and
the owner raises the alert threshold by hand; nothing changes automatically.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

WINDOW_NIGHTS = 14
MIN_PREDICTIONS = 20
FLOORS = {4: 70, 5: 85}  # percent, by |code|
CODES = tuple(range(5, -6, -1))  # +5 first


class Horizon(StrEnum):
    TONIGHT = "tonight"
    TOMORROW = "tomorrow"


@dataclass(frozen=True)
class Outcome:
    """``count`` predictions of ``code`` for the price update after ``night`` whose actual move
    was ``moved`` (+1 rose, -1 fell, 0 no change)."""

    night: date
    horizon: Horizon
    code: int
    moved: int
    count: int


@dataclass(frozen=True)
class Tally:
    hits: int = 0
    predictions: int = 0

    def __add__(self, other: Tally) -> Tally:
        return Tally(self.hits + other.hits, self.predictions + other.predictions)

    def below(self, floor_percent: int) -> bool:
        return self.hits * 100 < floor_percent * self.predictions


@dataclass(frozen=True)
class CodeAccuracy:
    code: int
    recent: Tally  # the last WINDOW_NIGHTS nights
    season: Tally


@dataclass(frozen=True)
class HorizonAccuracy:
    codes: tuple[CodeAccuracy, ...]  # codes with predictions this season, +5 first
    recent: Tally
    season: Tally


@dataclass(frozen=True)
class FloorBreach:
    horizon: Horizon
    code: int
    recent: Tally
    floor: int  # percent


@dataclass(frozen=True)
class AccuracyReport:
    tonight: HorizonAccuracy
    tomorrow: HorizonAccuracy
    breaches: tuple[FloorBreach, ...]

    @property
    def empty(self) -> bool:
        return self.tonight.season.predictions == 0 and self.tomorrow.season.predictions == 0


@dataclass
class _Counts:
    recent: dict[int, Tally] = field(default_factory=dict[int, Tally])
    season: dict[int, Tally] = field(default_factory=dict[int, Tally])


def price_accuracy(outcomes: Iterable[Outcome], *, last_night: date) -> AccuracyReport:
    """The report as of ``last_night``, the latest night whose price update has happened."""
    window_starts = last_night - timedelta(days=WINDOW_NIGHTS - 1)
    counts = {horizon: _Counts() for horizon in Horizon}
    for outcome in outcomes:
        hit = _sign(outcome.code) == outcome.moved
        tally = Tally(outcome.count if hit else 0, outcome.count)
        by_code = counts[outcome.horizon]
        by_code.season[outcome.code] = by_code.season.get(outcome.code, Tally()) + tally
        if window_starts <= outcome.night <= last_night:
            by_code.recent[outcome.code] = by_code.recent.get(outcome.code, Tally()) + tally
    breaches = tuple(
        FloorBreach(horizon, code, recent, FLOORS[abs(code)])
        for horizon in Horizon
        for code in CODES
        if abs(code) in FLOORS
        and (recent := counts[horizon].recent.get(code, Tally())).predictions >= MIN_PREDICTIONS
        and recent.below(FLOORS[abs(code)])
    )
    return AccuracyReport(
        tonight=_horizon(counts[Horizon.TONIGHT]),
        tomorrow=_horizon(counts[Horizon.TOMORROW]),
        breaches=breaches,
    )


def _horizon(counts: _Counts) -> HorizonAccuracy:
    codes = tuple(
        CodeAccuracy(code, counts.recent.get(code, Tally()), counts.season[code])
        for code in CODES
        if code in counts.season
    )
    return HorizonAccuracy(
        codes=codes,
        recent=sum(counts.recent.values(), Tally()),
        season=sum(counts.season.values(), Tally()),
    )


def _sign(code: int) -> int:
    return (code > 0) - (code < 0)
