"""Ticket 37: price snapshots, the nightly Price-change archive, the news log and ``/accuracy``.

The default clock is Thursday 19 Nov 2026, 18:00 UK (GMT). A night is the UK date before the
00:00 UK price update. Price fields are added to the shared ``bootstrap-static`` per test
(synthetic values); ``stats/price-changes/`` answers are built per test too.

Until the scheduler (ticket 31) drives them, a test asks for a night's planned runs, moves the
clock to each run's time and runs it through the harness's job helper.
"""

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fplbot.sources.fpl import FplResponse
from tests.harness import BotHarness, fpl_fixture

UK = ZoneInfo("Europe/London")
THURSDAY = date(2026, 11, 19)


def uk_time(moment: datetime) -> str:
    return f"{moment.astimezone(UK):%a %H:%M}"


def bootstrap(
    *,
    percent: dict[int, str] | None = None,
    codes: dict[int, tuple[int, int, int]] | None = None,
    news: dict[int, tuple[str, str]] | None = None,
    locked: dict[int, str] | None = None,
) -> FplResponse:
    """The shared ``bootstrap-static`` with price-change fields (everyone 0 unless given) and
    news (``news`` maps an id to (status, news text))."""
    data: dict[str, Any] = json.loads(fpl_fixture("bootstrap-static/").body)
    for element in data["elements"]:
        footballer = element["id"]
        nights = (codes or {}).get(footballer, (0, 0, 0))
        element["price_change_percent"] = (percent or {}).get(footballer, "0.0")
        element["price_change_hourly_rate"] = 10 * nights[0]
        element["price_change_calibrating"] = False
        element["price_change_locked_until"] = (locked or {}).get(footballer)
        element["price_change_projections"] = [
            {"offset": offset, "projected_percent": str(code * 20.0), "likelihood": code}
            for offset, code in enumerate(nights)
        ]
        status, text = (news or {}).get(footballer, (element.get("status", "a"), ""))
        element["status"], element["news"] = status, text
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


def rows(stored: str, table: str) -> list[str]:
    return [line for line in stored.splitlines() if line.startswith(f"{table}:")]


async def run_archive_runs(
    bot: BotHarness, night: date = THURSDAY, *, names: set[str] | None = None
) -> list[str]:
    """Run the night's planned archive runs (optionally only those named) in order, each at its
    time; '<name> <UK time>' of each run."""
    runs = [
        run
        for run in await bot.app.price_archive.planned_runs(night)
        if names is None or run.name in names
    ]
    for run in runs:
        if run.at > bot.clock.now():
            await bot.advance(run.at - bot.clock.now())
        await bot.run_job(run.name, run.job, run.priority)
    return [f"{run.name} {uk_time(run.at)}" for run in runs]


async def test_a_night_plans_news_reads_snapshots_and_the_archive(bot: BotHarness) -> None:
    runs = await bot.app.price_archive.planned_runs(THURSDAY)

    assert [f"{run.name} {uk_time(run.at)}" for run in runs] == [
        *(f"news-log Thu {hour:02d}:00" for hour in range(8, 18)),
        "price-snapshot Thu 18:00",
        "news-log Thu 19:00",
        "price-snapshot Thu 20:00",
        "news-log Thu 21:00",
        "price-snapshot Thu 22:00",
        "price-snapshot Thu 23:00",
        "price-snapshot Thu 23:45",
        "price-refresh Fri 00:05",
        "price-archive Fri 00:10",
    ]


async def test_snapshots_keep_a_compact_row_per_footballer_five_times_a_night(
    bot: BotHarness,
) -> None:
    bot.fpl.respond(
        "bootstrap-static/",
        bootstrap(
            percent={102: "-97.4"},
            codes={102: (-5, -5, 0)},
            locked={213: "2026-11-27T00:00:00Z"},
        ),
    )

    await run_archive_runs(bot, names={"price-snapshot"})

    snapshots = rows(await bot.database_text(), "price_snapshots")
    assert len(snapshots) == 5 * 16  # five times a night, every Footballer
    fakesson_at_18 = [r for r in snapshots if ", 102, " in r and "18, 0" in r]
    assert len(fakesson_at_18) == 1
    # price 8.0m, -97.4%, hourly rate, the three likelihoods, not locked, not calibrating
    assert fakesson_at_18[0].endswith(", 102, 80, -974, -50, -5, -5, 0, None, False)")
    locked = [r for r in snapshots if ", 213, " in r]
    assert all("2026, 11, 27" in r for r in locked)
