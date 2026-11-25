"""Rendering helpers shared by the Rival gap (``/rivals``) and the Elite gap (``/gap``): one
Footballer's line in the prototype's shape, signed edges and whole percents."""

from decimal import ROUND_HALF_UP, Decimal

from fplbot.advice.gap import Backing, GapLine
from fplbot.delivery import texts
from fplbot.store.squads import Squad

# A captain share below this is not worth a mention on a line (prototype).
CAPTAIN_WORTH_MENTIONING = 0.05


def backing(squad: Squad) -> Backing:
    captain = next((p.footballer_id for p in squad.xi + squad.bench if p.is_captain), None)
    return Backing(frozenset(p.footballer_id for p in squad.xi), captain)


def xi_line(line: GapLine, names: dict[int, str]) -> str:
    captain = None
    if line.you_captain or line.reference.captain >= CAPTAIN_WORTH_MENTIONING:
        captain = (line.you_captain, percent(line.reference.captain))
    return texts.rivals_line(
        name(names, line.footballer_id),
        line.you_start,
        percent(line.reference.xi),
        captain,
        signed(line.edge),
    )


def name(names: dict[int, str], footballer: int | None) -> str:
    if footballer is None:
        return texts.NOBODY
    return names.get(footballer, texts.unknown_footballer(footballer))


def percent(share: float) -> int:
    return int(Decimal(str(share * 100)).quantize(Decimal(1), ROUND_HALF_UP))


def signed(edge: float) -> str:
    """``+4.0`` / ``−3.5`` (a true minus sign, as in the prototype), half rounded up."""
    size = Decimal(str(abs(edge))).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return f"{'+' if edge >= 0 else '−'}{size}"
