"""Turning what a Member types ("Ljubljana", "new york", "europe/berlin") into an IANA zone."""

from functools import cache
from zoneinfo import available_timezones

# The four timezone buttons, in order (ticket 14 prototype).
BUTTON_ZONES = ("Europe/London", "Europe/Paris", "America/New_York", "Asia/Kolkata")


def resolve_timezone(typed: str) -> str | None:
    """An IANA zone name matching ``typed`` (a zone name or a city), ignoring case and treating
    spaces as underscores; ``None`` if nothing matches."""
    key = "_".join(typed.strip().lower().split())
    if not key:
        return None
    zones, cities = _lookup()
    return zones.get(key) or cities.get(key)


@cache
def _lookup() -> tuple[dict[str, str], dict[str, str]]:
    # Only "Area/City" zones: no legacy aliases like "US/Eastern" or "Etc/GMT+3" as cities.
    names = sorted(available_timezones())
    zones = {name.lower(): name for name in names}
    cities: dict[str, str] = {}
    for name in names:
        area, _, city = name.rpartition("/")
        if area and area.split("/")[0] not in ("Etc", "SystemV", "US", "Brazil", "Canada"):
            cities.setdefault(city.lower(), name)
    return zones, cities
