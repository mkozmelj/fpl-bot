"""Renders a Price alert decision (``advice.price_alert``) as one plain-text message."""

from fplbot.advice.price_alert import AlertLine, PriceAlert
from fplbot.delivery import texts


def render_price_alert(alert: PriceAlert) -> str:
    blocks = [texts.price_alert_header(alert.gameweek)]
    if alert.falls:
        blocks.append("\n".join([texts.PRICE_FALLS, *map(_line, alert.falls)]))
    if alert.rises:
        blocks.append("\n".join([texts.PRICE_RISES, *map(_line, alert.rises)]))
    footer: list[str] = []
    if alert.tomorrow:
        footer.append(texts.price_alert_tomorrow([(m.name, m.rise) for m in alert.tomorrow]))
    if alert.falls and alert.rises:
        footer.append(texts.PRICE_SAVING_BOTH)
    elif alert.falls:
        footer.append(texts.PRICE_SAVING_FALLS)
    else:
        footer.append(texts.PRICE_SAVING_RISES)
    if alert.squad_may_be_stale:
        footer.append(texts.PRICE_STALE_SQUAD)
    blocks.append("\n".join(footer))
    return "\n\n".join(blocks)


def _line(line: AlertLine) -> str:
    text = texts.price_alert_line(
        line.name,
        line.position,
        line.club,
        line.price,
        line.new_price,
        texts.VERY_LIKELY if line.very_likely else texts.LIKELY,
    )
    return f"{text} · {line.availability}" if line.availability else text
