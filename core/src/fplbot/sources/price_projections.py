"""FPL's price-change projections, read from ``bootstrap-static`` (research 04, ticket 15).

Each Footballer has ``price_change_projections``: one entry per coming price update
(``offset`` 0 is tonight's 00:00 UK update, 1 tomorrow night's) with a ``likelihood`` code from
-5 to +5. ``price_change_calibrating`` is true while FPL is still calibrating its predictor;
such a Footballer's codes are not used.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fplbot.sources.fpl import FplBadData, reference_in


class Availability(StrEnum):
    """FPL's status flag for a Footballer who may not play."""

    DOUBTFUL = "doubtful"
    INJURED = "injured"
    SUSPENDED = "suspended"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class FootballerPrice:
    """One Footballer's price outlook at alert time."""

    id: int
    name: str
    position: str  # GKP, DEF, MID or FWD
    club: str  # short club name
    price: int  # tenths of a million: 65 is £6.5m
    availability: Availability | None  # None: available
    # FPL's likelihood codes for tonight's and tomorrow night's price update; None when FPL
    # has no usable projection (missing, or the Footballer is still calibrating).
    tonight: int | None
    tomorrow: int | None


_AVAILABILITY = {
    "d": Availability.DOUBTFUL,
    "i": Availability.INJURED,
    "s": Availability.SUSPENDED,
    "u": Availability.UNAVAILABLE,
    "n": Availability.UNAVAILABLE,
}


def price_projections(bootstrap: dict[str, Any]) -> dict[int, FootballerPrice]:
    """Every Footballer's price outlook, by id. Raises ``FplBadData`` when the response has no
    projection fields at all (FPL dropped or renamed them): a data failure, not a quiet night.
    A Footballer without usable codes has ``tonight``/``tomorrow`` of ``None``."""
    footballers = {f.id: f for f in reference_in(bootstrap).footballers}
    elements: list[dict[str, Any]] = bootstrap["elements"]
    if not any("price_change_projections" in element for element in elements):
        raise FplBadData(200)
    prices: dict[int, FootballerPrice] = {}
    for element in elements:
        footballer = footballers[int(element["id"])]
        codes = _codes(element)
        prices[footballer.id] = FootballerPrice(
            id=footballer.id,
            name=footballer.web_name,
            position=footballer.position,
            club=footballer.club,
            price=footballer.now_cost,
            availability=_AVAILABILITY.get(str(element.get("status") or "a")),
            tonight=codes.get(0),
            tomorrow=codes.get(1),
        )
    return prices


def _codes(element: dict[str, Any]) -> dict[int, int]:
    """Likelihood codes by offset; empty when calibrating or unusable."""
    if element.get("price_change_calibrating") is not False:
        return {}
    projections = element.get("price_change_projections")
    if not isinstance(projections, list):
        return {}
    codes: dict[int, int] = {}
    for projection in projections:  # pyright: ignore[reportUnknownVariableType]
        try:
            offset = int(projection["offset"])  # pyright: ignore[reportUnknownArgumentType]
            code = int(projection["likelihood"])  # pyright: ignore[reportUnknownArgumentType]
        except KeyError, TypeError, ValueError:
            continue
        if -5 <= code <= 5:
            codes[offset] = code
    return codes
