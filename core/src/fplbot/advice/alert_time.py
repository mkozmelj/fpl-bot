"""When a Member's Price alert goes out (ticket 15): their chosen local time, clamped to the
17:00-23:15 UK window so it always lands before the 00:00 UK price update."""

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
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
    wanted = datetime.combine(on, chosen, timezone).astimezone(UK)
    opens = datetime.combine(wanted.date(), WINDOW_OPENS, UK)
    closes = datetime.combine(wanted.date(), WINDOW_CLOSES, UK)
    at = min(max(wanted, opens), closes)
    return AlertSendTime(at=at, clamped=at != wanted)
