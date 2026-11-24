"""Price and news history read from FPL (ticket 37, research 04): what the snapshots, the
nightly Price-change archive and the news log keep. Plain data out; raw responses are dropped.

- ``price_snapshot(bootstrap)``: each Footballer's price-change state (price, progress percent,
  hourly rate, the three likelihood codes, lock flags). Fields FPL leaves out are ``None``.
- ``news_states(bootstrap)``: each Footballer's status flag and news text.
- ``price_changes(data)``: the rows of ``stats/price-changes/`` (a rolling window of about six
  weeks, so it is archived every night). Its top-level shape is unverified: a list of rows, or
  an object holding that list, are both read.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from fplbot.sources.fpl import FplBadData

UK = ZoneInfo("Europe/London")
# A change is stamped a few seconds after 00:00 UK; going back half a day lands on its night.
_TO_NIGHT = timedelta(hours=12)


@dataclass(frozen=True)
class FplPriceSnapshot:
    footballer_id: int
    price: int  # tenths of a million
    percent: int | None  # tenths of a percent: -974 is -97.4%
    hourly_rate: int | None
    # Likelihood codes (-5..+5) for the coming three price updates; None when FPL gives none.
    likelihoods: tuple[int | None, int | None, int | None]
    locked_until: datetime | None
    calibrating: bool | None


@dataclass(frozen=True)
class FplNews:
    footballer_id: int
    status: str  # FPL's flag: a, d, i, s, u or n
    news: str


@dataclass(frozen=True)
class FplPriceChange:
    footballer_id: int
    club_id: int | None
    gameweek: int | None
    changed_at: datetime
    cost_before: int
    cost_after: int

    @property
    def night(self) -> date:
        """The UK date before the 00:00 UK price update that made this change."""
        return (self.changed_at.astimezone(UK) - _TO_NIGHT).date()


def price_snapshot(bootstrap: dict[str, Any]) -> list[FplPriceSnapshot]:
    try:
        return [_snapshot(element) for element in _elements(bootstrap)]
    except KeyError, TypeError, ValueError:
        raise FplBadData(200) from None


def news_states(bootstrap: dict[str, Any]) -> list[FplNews]:
    try:
        return [
            FplNews(
                footballer_id=int(element["id"]),
                status=str(element.get("status") or "a"),
                news=str(element.get("news") or ""),
            )
            for element in _elements(bootstrap)
        ]
    except KeyError, TypeError, ValueError:
        raise FplBadData(200) from None


def price_changes(data: Any) -> list[FplPriceChange]:
    """Raises ``FplBadData`` when the answer has no readable rows list or a row is unreadable."""
    rows = _rows(data)
    try:
        return [
            FplPriceChange(
                footballer_id=int(row["element"]),
                club_id=_optional_int(row.get("team")),
                gameweek=_optional_int(row.get("event")),
                changed_at=_when(row["changed_at"]),
                cost_before=int(row["cost_before"]),
                cost_after=int(row["cost_after"]),
            )
            for row in rows
        ]
    except KeyError, TypeError, ValueError, AttributeError:
        raise FplBadData(200) from None


def _elements(bootstrap: dict[str, Any]) -> list[dict[str, Any]]:
    elements = bootstrap["elements"]
    if not isinstance(elements, list):
        raise TypeError
    return elements  # pyright: ignore[reportUnknownVariableType]


def _snapshot(element: dict[str, Any]) -> FplPriceSnapshot:
    locked = element.get("price_change_locked_until")
    calibrating = element.get("price_change_calibrating")
    return FplPriceSnapshot(
        footballer_id=int(element["id"]),
        price=int(element["now_cost"]),
        percent=_tenths(element.get("price_change_percent")),
        hourly_rate=_optional_int(element.get("price_change_hourly_rate")),
        likelihoods=_likelihoods(element.get("price_change_projections")),
        locked_until=_when(locked) if locked else None,
        calibrating=calibrating if isinstance(calibrating, bool) else None,
    )


def _likelihoods(projections: Any) -> tuple[int | None, int | None, int | None]:
    codes: dict[int, int] = {}
    if isinstance(projections, list):
        for projection in projections:  # pyright: ignore[reportUnknownVariableType]
            try:
                offset = int(projection["offset"])  # pyright: ignore[reportUnknownArgumentType]
                code = int(projection["likelihood"])  # pyright: ignore[reportUnknownArgumentType]
            except KeyError, TypeError, ValueError:
                continue
            if -5 <= code <= 5:
                codes[offset] = code
    return codes.get(0), codes.get(1), codes.get(2)


def _rows(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        data = lists[0] if len(lists) == 1 else None  # pyright: ignore[reportUnknownVariableType]
    if not isinstance(data, list):
        raise FplBadData(200)
    return data  # pyright: ignore[reportUnknownVariableType]


def _tenths(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int((Decimal(str(value)) * 10).to_integral_value())
    except InvalidOperation:
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except TypeError, ValueError:
        return None


def _when(value: Any) -> datetime:
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError
    return moment
