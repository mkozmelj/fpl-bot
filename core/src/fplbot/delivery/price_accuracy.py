"""Renders the ``/accuracy`` report (``advice.price_accuracy``) as one plain-text message."""

from fplbot.advice.price_accuracy import (
    MIN_PREDICTIONS,
    WINDOW_NIGHTS,
    AccuracyReport,
    HorizonAccuracy,
    Tally,
)
from fplbot.delivery import texts
from fplbot.store.price_history import Horizon


def render_accuracy(report: AccuracyReport, season: str) -> str:
    if report.empty:
        return texts.ACCURACY_EMPTY
    blocks = [
        "\n".join([texts.accuracy_header(season), texts.ACCURACY_HIT]),
        _section(report.tonight, tomorrow=False),
        _section(report.tomorrow, tomorrow=True),
    ]
    if report.breaches:
        lines = [
            texts.accuracy_breach(
                b.horizon is Horizon.TOMORROW, _code(b.code), _tally(b.recent), b.floor
            )
            for b in report.breaches
        ]
        blocks.append("\n".join([*lines, texts.ACCURACY_MANUAL]))
    else:
        blocks.append(texts.accuracy_floors_met(WINDOW_NIGHTS, MIN_PREDICTIONS))
    return "\n\n".join(blocks)


def _section(accuracy: HorizonAccuracy, *, tomorrow: bool) -> str:
    lines = [texts.accuracy_section(tomorrow, WINDOW_NIGHTS)]
    lines.extend(
        texts.accuracy_line(_code(c.code), _tally(c.recent), _tally(c.season))
        for c in accuracy.codes
    )
    lines.append(
        texts.accuracy_line(texts.ACCURACY_TOTAL, _tally(accuracy.recent), _tally(accuracy.season))
    )
    return "\n".join(lines)


def _code(code: int) -> str:
    return f"{code:+d}" if code else "0"


def _tally(tally: Tally) -> str:
    percent = round(100 * tally.hits / tally.predictions) if tally.predictions else None
    return texts.accuracy_tally(tally.hits, tally.predictions, percent)
