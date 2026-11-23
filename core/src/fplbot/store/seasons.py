"""FPL seasons. Every table carries a ``season`` column such as ``"2026-27"``."""

from datetime import datetime

# A new FPL season's game opens in July; until then the previous season is current.
_SEASON_START_MONTH = 7


def season_of(moment: datetime) -> str:
    """The FPL season a moment belongs to. Ticket 40's owner-confirmed ``/rollover`` will make
    the current season explicit state; until then it follows the calendar."""
    first_year = moment.year if moment.month >= _SEASON_START_MONTH else moment.year - 1
    return f"{first_year}-{(first_year + 1) % 100:02d}"
