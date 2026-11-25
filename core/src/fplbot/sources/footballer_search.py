"""Footballers by name (ticket 29), over the Footballers ``FplSource.reference()`` parses from
the in-memory ``bootstrap-static``. This module never stores anything.

Name search is accent- and case-insensitive and follows the prototype's "contains" match, with
one refinement for a full-size Footballer list: if any Footballer matches word by word (every
typed word starts a word of his name: "aurelio", "a mensah", "nunez"), only those count; a plain
substring match ("ensa") is the fallback.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence

from fplbot.sources.fpl import FplFootballer

_WORD = re.compile(r"[a-z0-9]+")


def search(footballers: Iterable[FplFootballer], query: str) -> list[FplFootballer]:
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


def _names(footballer: FplFootballer) -> tuple[str, str]:
    return _fold(footballer.web_name), _fold(footballer.full_name)


def _words(footballer: FplFootballer) -> list[str]:
    return [word for name in _names(footballer) for word in _WORD.findall(name)]


def _starts_words(typed: Sequence[str], words: Sequence[str]) -> bool:
    return all(any(word.startswith(t) for word in words) for t in typed)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
