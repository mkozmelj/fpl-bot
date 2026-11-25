"""When a Member's Price alert goes out (ticket 15): their chosen local time, clamped to the
17:00-23:15 UK window so it always lands before the 00:00 UK price update."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fplbot.clock import UK_ZONE

WINDOW_OPENS = time(17, 0)
WINDOW_CLOSES = time(23, 15)


@dataclass(frozen=True)
class AlertSendTime:
    at: datetime  # in UK time
    clamped: bool  # the chosen time fell outside the window


def price_alert_send_time(chosen: time, timezone: ZoneInfo, on: date) -> AlertSendTime:
    """When the alert chosen for ``chosen`` local time on local date ``on`` is sent.

    The chosen time is converted to UK time and clamped to the window on that UK day: earlier
    times go out at 17:00 UK, later ones at 23:15 UK.
    """
    wanted = datetime.combine(on, chosen, timezone).astimezone(UK_ZONE)
    opens = datetime.combine(wanted.date(), WINDOW_OPENS, UK_ZONE)
    closes = datetime.combine(wanted.date(), WINDOW_CLOSES, UK_ZONE)
    at = min(max(wanted, opens), closes)
    return AlertSendTime(at=at, clamped=at != wanted)


def send_time_on_night(chosen: time, timezone: ZoneInfo, night: date) -> AlertSendTime:
    """When the alert chosen for ``chosen`` local time goes out on UK night ``night`` (the UK
    date whose following 00:00 price update it warns about). Far from the UK the Member's local
    date that evening can be the day before or after ``night``; the UK time of day is the one
    ``/time`` told them."""
    for days in (0, -1, 1):
        send = price_alert_send_time(chosen, timezone, night + timedelta(days=days))
        if send.at.date() == night:
            return send
    raise AssertionError("every local date maps onto a UK date within a day")  # pragma: no cover


def send_times_on_night(settings: Iterable[tuple[time, ZoneInfo]], night: date) -> list[datetime]:
    """The distinct UK send times on ``night`` for Members' (alert time, timezone) settings,
    earliest first. Members sharing a time share one run, and so one ``bootstrap-static`` fetch."""
    return sorted({send_time_on_night(chosen, zone, night).at for chosen, zone in settings})
