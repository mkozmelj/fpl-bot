"""What one Member's nightly Price alert says (ticket 15). Plain data in, a decision out.

Built on FPL's own price-change likelihood codes (-5..+5) for the coming price updates:
- tonight: owned Footballers Likely (-4) or Very likely (-5) to fall, and Watch-list Footballers
  Likely (+4) or Very likely (+5) to rise. Other directions are never mentioned.
- tomorrow night: the same, Very likely (+/-5) only, leaving out anyone listed tonight. The
  night after is never shown.
A night with nothing for tonight but a Very likely change tomorrow night sends that heads-up
alone (story 46); a night with neither is quiet (story 50).
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from fplbot.sources.price_projections import Availability, FootballerPrice

LIKELY = 4
VERY_LIKELY = 5
PRICE_STEP = 1  # FPL prices move by £0.1m (one tenth of a million) a night


@dataclass(frozen=True)
class AlertLine:
    name: str
    position: str
    club: str
    price: int
    new_price: int
    very_likely: bool
    availability: Availability | None  # shown for owned Footballers only


@dataclass(frozen=True)
class TomorrowMention:
    name: str
    rise: bool


@dataclass(frozen=True)
class PriceAlert:
    gameweek: int
    falls: tuple[AlertLine, ...]  # owned, Very likely first, then by name
    rises: tuple[AlertLine, ...]  # Watch list, Very likely first, then by name
    tomorrow: tuple[TomorrowMention, ...]  # falls first, then rises, each by name
    squad_may_be_stale: bool


def price_alert(
    *,
    gameweek: int,
    owned: Collection[int],
    watched: Sequence[int],
    prices: Mapping[int, FootballerPrice],
    squad_may_be_stale: bool,
) -> PriceAlert | None:
    """The Member's alert for tonight (possibly only tomorrow night's heads-up), or ``None`` on
    a quiet night. Ids missing from ``prices`` are skipped."""
    mine = [prices[i] for i in dict.fromkeys(owned) if i in prices]
    watching = [prices[i] for i in dict.fromkeys(watched) if i in prices]
    falling = [p for p in mine if _likely(p.tonight, rise=False, at_least=LIKELY)]
    rising = [p for p in watching if _likely(p.tonight, rise=True, at_least=LIKELY)]
    listed = {p.id for p in (*falling, *rising)}
    tomorrow = (
        *_tomorrow(mine, listed, rise=False),
        *_tomorrow(watching, listed, rise=True),
    )
    if not falling and not rising and not tomorrow:
        return None
    return PriceAlert(
        gameweek=gameweek,
        falls=_lines(falling, rise=False),
        rises=_lines(rising, rise=True),
        tomorrow=tomorrow,
        squad_may_be_stale=squad_may_be_stale,
    )


def squad_may_be_stale(
    *,
    squad_gameweek: int | None,
    last_gameweek: int | None,
    next_deadline: datetime | None,
    price_update: datetime,
) -> bool:
    """Whether a Member may have sold some of "their" Footballers: the stored Squad is older
    than the last deadline's, or it is the night before a deadline (the deadline comes before
    the following night's price update), when transfers are most likely."""
    if squad_gameweek is not None and last_gameweek is not None and squad_gameweek < last_gameweek:
        return True
    return next_deadline is not None and next_deadline <= price_update + timedelta(days=1)


def _likely(code: int | None, *, rise: bool, at_least: int) -> bool:
    if code is None:
        return False
    return code >= at_least if rise else code <= -at_least


def _lines(footballers: Iterable[FootballerPrice], *, rise: bool) -> tuple[AlertLine, ...]:
    lines = [
        AlertLine(
            name=p.name,
            position=p.position,
            club=p.club,
            price=p.price,
            new_price=p.price + PRICE_STEP if rise else p.price - PRICE_STEP,
            very_likely=_likely(p.tonight, rise=rise, at_least=VERY_LIKELY),
            availability=None if rise else p.availability,
        )
        for p in footballers
    ]
    return tuple(sorted(lines, key=lambda line: (not line.very_likely, line.name)))


def _tomorrow(
    footballers: Iterable[FootballerPrice], listed: Collection[int], *, rise: bool
) -> list[TomorrowMention]:
    return sorted(
        (
            TomorrowMention(p.name, rise=rise)
            for p in footballers
            if p.id not in listed and _likely(p.tomorrow, rise=rise, at_least=VERY_LIKELY)
        ),
        key=lambda mention: mention.name,
    )
