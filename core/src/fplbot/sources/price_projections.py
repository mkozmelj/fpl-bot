"""FPL's price-change projections, read from ``bootstrap-static`` (research 04, ticket 15).

Each Footballer has ``price_change_projections``: one entry per coming price update
(``offset`` 0 is tonight's 00:00 UK update, 1 tomorrow night's) with a ``likelihood`` code from
-5 to +5. ``price_change_calibrating`` is true while FPL is still calibrating its predictor;
such a Footballer's codes are not used.
"""

from typing import Any

from fplbot.advice.price_alert import Availability, FootballerPrice
from fplbot.sources.footballer_search import footballers_in
from fplbot.sources.fpl import FplBadData

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
    try:
        footballers = footballers_in(bootstrap)
        elements: list[dict[str, Any]] = bootstrap["elements"]
    except KeyError, TypeError, ValueError:
        raise FplBadData(200) from None
    if not any("price_change_projections" in element for element in elements):
        raise FplBadData(200)
    prices: dict[int, FootballerPrice] = {}
    for element in elements:
        footballer = footballers[int(element["id"])]
        codes = _codes(element)
        prices[footballer.id] = FootballerPrice(
            id=footballer.id,
            name=footballer.name,
            position=footballer.position,
            club=footballer.club,
            price=footballer.price_tenths,
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
