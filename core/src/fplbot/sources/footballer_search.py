"""Footballers by name, read from the in-memory ``bootstrap-static`` (ticket 29).

Only what the Watch list needs: a name to show, club, position and price. Persistent reference
data (Footballers kept across seasons) is ticket 30's; this module never stores anything.

Name search is accent- and case-insensitive and follows the prototype's "contains" match, with
one refinement for a full-size Footballer list: if any Footballer matches word by word (every
typed word starts a word of his name: "aurelio", "a mensah", "nunez"), only those count; a plain
substring match ("ensa") is the fallback.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Footballer:
    id: int  # FPL element id: only meaningful within one season
    name: str  # FPL's short display name (web_name)
    full_name: str
    club: str  # short club name, e.g. "ARS"
    position: str  # GKP, DEF, MID or FWD
    price_tenths: int  # FPL's now_cost: £0.1m units

    @property
    def price(self) -> str:
        return f"£{self.price_tenths / 10:.1f}m"


def footballers_in(bootstrap: dict[str, Any]) -> dict[int, Footballer]:
    """Every Footballer in a ``bootstrap-static`` response, by id. Raises ``KeyError``,
    ``TypeError`` or ``ValueError`` on a response of the wrong shape."""
    clubs = {int(team["id"]): str(team["short_name"]) for team in bootstrap["teams"]}
    positions = {
        int(kind["id"]): str(kind["singular_name_short"]) for kind in bootstrap["element_types"]
    }
    footballers: dict[int, Footballer] = {}
    for element in bootstrap["elements"]:
        first = str(element.get("first_name") or "")
        second = str(element.get("second_name") or "")
        footballer = Footballer(
            id=int(element["id"]),
            name=str(element["web_name"]),
            full_name=f"{first} {second}".strip(),
            club=clubs.get(int(element["team"]), "?"),
            position=positions.get(int(element["element_type"]), "?"),
            price_tenths=int(element["now_cost"]),
        )
        footballers[footballer.id] = footballer
    return footballers


def search(footballers: Iterable[Footballer], query: str) -> list[Footballer]:
    """Footballers whose name matches ``query``, in the given order."""
    typed = _fold(query)
    typed_words = _WORD.findall(typed)
    if not typed_words:
        return []
    candidates = list(footballers)
    by_words = [f for f in candidates if _starts_words(typed_words, _words(f))]
    if by_words:
        return by_words
    compact = "".join(typed_words)
    return [f for f in candidates if any(compact in "".join(_WORD.findall(n)) for n in _names(f))]


def _names(footballer: Footballer) -> tuple[str, str]:
    return _fold(footballer.name), _fold(footballer.full_name)


def _words(footballer: Footballer) -> list[str]:
    return [word for name in _names(footballer) for word in _WORD.findall(name)]


def _starts_words(typed: Sequence[str], words: Sequence[str]) -> bool:
    return all(any(word.startswith(t) for word in words) for t in typed)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
