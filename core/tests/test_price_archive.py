"""Ticket 37: price snapshots, the nightly Price-change archive, the news log and ``/accuracy``.

The default clock is Thursday 19 Nov 2026, 18:00 UK (GMT, so UK and UTC times match). A night is
the UK date before the 00:00 UK price update. Price fields and news are added to the shared
``bootstrap-static`` per test (synthetic values); ``stats/price-changes/`` answers are built per
test too (the shared fixture holds two older changes).

Most tests start the bot's scheduler and let simulated time pass; the floor tests drive the
night's Price alert and archive runs directly, so they can jump two weeks ahead cheaply.
"""

import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fplbot.sources.fpl import FplResponse, Priority
from tests.harness import BotHarness, fpl_fixture

UK = ZoneInfo("Europe/London")
THURSDAY = date(2026, 11, 19)
FRIDAY = date(2026, 11, 20)
STARTUP_TIME = timedelta(minutes=1)

type Codes = tuple[int, int, int]


def uk(night: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(night, time(hour, minute), UK)


def uk_time(moment: datetime) -> str:
    return f"{moment.astimezone(UK):%a %H:%M}"


async def advance_to(bot: BotHarness, moment: datetime) -> None:
    await bot.advance(moment - bot.clock.now())


def bootstrap(
    *,
    codes: dict[int, Codes] | None = None,
    percent: dict[int, str] | None = None,
    news: dict[int, tuple[str, str]] | None = None,
    locked: dict[int, str] | None = None,
    extra: int = 0,
) -> FplResponse:
    """The shared ``bootstrap-static`` with price-change fields (codes 0 unless given in
    ``codes``: tonight, tomorrow night, the night after) and news (``news``: id -> (status,
    text)). ``extra`` adds that many more Footballers, ids 301 on."""
    data: dict[str, Any] = json.loads(fpl_fixture("bootstrap-static/").body)
    template = data["elements"][-1]
    for n in range(extra):
        data["elements"].append({**template, "id": 301 + n, "web_name": f"Extra{n + 1}"})
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


def price_changes(*changes: tuple[int, date, int, int]) -> FplResponse:
    """A ``stats/price-changes/`` answer: (Footballer id, night, cost before, cost after), each
    stamped a few seconds after the 00:00 UK update that ends the night."""
    rows = [
        {
            "element": footballer,
            "team": 1,
            "event": 11,
            "changed_at": (uk(night + timedelta(days=1), 0) + timedelta(seconds=4)).isoformat(),
            "cost_before": before,
            "cost_after": after,
        }
        for footballer, night, before, after in changes
    ]
    return FplResponse(200, json.dumps(rows).encode(), {"content-type": "application/json"})


def rows(stored: str, table: str) -> list[str]:
    return [line for line in stored.splitlines() if line.startswith(f"{table}:")]


def first_time(row: str) -> str:
    """The first timestamp in a stored row (as UK = UTC in November), e.g. 'Thu 18:00'."""
    match = re.search(r"datetime\.datetime\((\d+), (\d+), (\d+), (\d+), (\d+)", row)
    assert match, row
    year, month, day, hour, minute = map(int, match.groups())
    return uk_time(datetime(year, month, day, hour, minute, tzinfo=UK))


def requests_to(bot: BotHarness, path: str) -> int:
    return sum(1 for r in bot.fpl.requests if r.path == path)


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
            codes={102: (-5, -4, 0)},
            locked={213: "2026-11-27T00:00:00Z"},
        ),
    )
    await bot.start_scheduling()

    await advance_to(bot, uk(FRIDAY, 1))

    snapshots = rows(await bot.database_text(), "price_snapshots")
    assert sorted({first_time(r) for r in snapshots}) == [
        "Thu 18:00",
        "Thu 20:00",
        "Thu 22:00",
        "Thu 23:00",
        "Thu 23:45",
    ]
    assert len(snapshots) == 5 * 16  # every Footballer each time
    fakesson = [r for r in snapshots if ", 102, " in r and first_time(r) == "Thu 18:00"]
    # £8.0m, -97.4%, hourly rate -50, likelihoods -5/-4/0, not locked, not calibrating
    assert [r.split(", 102, ")[1] for r in fakesson] == ["80, -974, -50, -5, -4, 0, None, False)"]
    lastpick = [r for r in snapshots if ", 213, " in r]
    assert all("datetime.datetime(2026, 11, 27, 0, 0" in r for r in lastpick)


async def test_a_missed_snapshot_is_skipped_not_back_filled(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap())
    await advance_to(bot, uk(THURSDAY, 20, 10))  # the bot was down at 20:00

    await bot.start_scheduling()
    await advance_to(bot, uk(FRIDAY, 1))

    snapshots = rows(await bot.database_text(), "price_snapshots")
    assert sorted({first_time(r) for r in snapshots}) == ["Thu 22:00", "Thu 23:00", "Thu 23:45"]


async def test_the_00_10_archive_stores_price_changes_once_per_night(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap())
    await bot.start_scheduling()
    await bot.advance(STARTUP_TIME)  # catches up Wednesday's archive from the shared fixture
    bot.fpl.respond(
        "stats/price-changes/",
        price_changes((102, THURSDAY, 80, 79), (209, THURSDAY, 95, 96)),
    )
    fetched_before = requests_to(bot, "stats/price-changes")

    await advance_to(bot, uk(FRIDAY, 0, 30))
    stored = await bot.database_text()
    await bot.restart()  # inside the archive's catch-up window: the run fires again
    await advance_to(bot, uk(FRIDAY, 1))

    changes = rows(stored, "price_changes")
    assert len(changes) == 2 + 2  # Thursday's two, and the shared fixture's two older ones
    assert any(", 102, " in r and "79)" in r for r in changes)
    archived = [r.split(", ")[2] for r in rows(stored, "job_completions") if "price_archive" in r]
    assert sorted(archived) == ["'2026-11-18'", "'2026-11-19'"]  # Wednesday and Thursday
    # The re-run found the night's completion row: no request, nothing new stored.
    assert requests_to(bot, "stats/price-changes") - fetched_before == 1
    assert rows(await bot.database_text(), "price_changes") == changes


async def test_the_news_log_gains_a_row_only_when_news_or_status_changes(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap())
    await bot.start_scheduling()
    await advance_to(bot, uk(THURSDAY, 18, 30))
    first_read = rows(await bot.database_text(), "footballer_news")

    bot.fpl.respond(
        "bootstrap-static/",
        bootstrap(news={208: ("d", "Hamstring injury - 75% chance of playing")}),
    )
    await advance_to(bot, uk(THURSDAY, 23, 59))
    later = rows(await bot.database_text(), "footballer_news")

    assert len(first_read) == 16  # the first read records everyone once
    [change] = later[16:]  # six more reads from 19:00 to 23:45, one change
    assert first_time(change) == "Thu 19:00"
    assert ", 208, " in change
    assert change.endswith("'d', 'Hamstring injury - 75% chance of playing')")


async def test_accuracy_shows_hit_rates_per_code_for_tonight_and_tomorrow(
    bot: BotHarness,
) -> None:
    thursday = bootstrap(codes={102: (-5, -5, 0), 103: (-5, 0, 0), 209: (4, 4, 0), 101: (4, 0, 0)})
    friday = bootstrap(codes={102: (-4, 0, 0), 209: (5, 0, 0)})
    bot.fpl.respond("bootstrap-static/", thursday)
    await bot.active_member(user_id=2001, team_id=1001)  # alert at 20:00 UK
    await bot.start_scheduling()
    await bot.advance(STARTUP_TIME)
    thursday_changes = [
        (102, THURSDAY, 80, 79),  # -5 fell: hit
        (209, THURSDAY, 95, 96),  # +4 rose: hit
        (101, THURSDAY, 45, 44),  # +4 fell: miss
        (210, THURSDAY, 60, 61),  # 0 rose: miss
    ]
    bot.fpl.respond("stats/price-changes/", price_changes(*thursday_changes))

    await advance_to(bot, uk(FRIDAY, 12))
    bot.fpl.respond("bootstrap-static/", friday)
    bot.fpl.respond(
        "stats/price-changes/",
        price_changes(*thursday_changes, (209, FRIDAY, 96, 97)),  # the window keeps Thursday
    )
    await advance_to(bot, uk(date(2026, 11, 21), 9))

    await bot.owner.send("/accuracy")

    # Friday's "tomorrow" codes wait for Saturday night's archive.
    assert bot.owner.last_reply == (
        "Price predictor accuracy · 2026-27\n"
        "A hit: a + code rose, a - code fell, 0 stayed.\n"
        "\n"
        "Tonight's code · last 14 nights · season\n"
        "+5  1/1 100% · 1/1 100%\n"
        "+4  1/2 50% · 1/2 50%\n"
        "0  25/26 96% · 25/26 96%\n"
        "-4  0/1 0% · 0/1 0%\n"
        "-5  1/2 50% · 1/2 50%\n"
        "All  28/32 88% · 28/32 88%\n"
        "\n"
        "Tomorrow night's code · last 14 nights · season\n"
        "+4  1/1 100% · 1/1 100%\n"
        "0  14/14 100% · 14/14 100%\n"
        "-5  0/1 0% · 0/1 0%\n"
        "All  15/16 94% · 15/16 94%\n"
        "\n"
        "Floors (±4 70%, ±5 85%; last 14 nights, 20+ predictions a code): all met."
    )


async def test_accuracy_before_any_archived_night_says_nothing_is_scored(
    bot: BotHarness,
) -> None:
    await bot.owner.send("/accuracy")

    assert bot.owner.last_reply == (
        "Price predictor accuracy: nothing scored yet. A night's codes are scored once its "
        "00:10 price-change archive is stored."
    )


async def test_accuracy_from_a_member_or_a_stranger_gets_no_reply(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    stranger = bot.private_chat(4242)
    before = len(alice.replies)

    await alice.send("/accuracy")
    await stranger.send("/accuracy")

    assert len(alice.replies) == before
    assert stranger.replies == []


async def run_night_directly(bot: BotHarness, night: date) -> None:
    """The night's Price alerts and its archive, each run at its planned time."""
    alerts = await bot.app.price_alerts.planned_runs(night)
    archive = bot.app.price_archive.archive_job(night)
    for run in alerts:
        await advance_to(bot, run.at)
        await bot.run_job(run.name, run.job, run.priority)
    await advance_to(bot, uk(night + timedelta(days=1), 0, 10))
    await bot.run_job("price-archive", archive, Priority.ROUTINE)


async def test_the_floor_flag_needs_20_predictions_in_14_nights_below_the_floor(
    bot: BotHarness,
) -> None:
    falls = range(301, 326)  # 25 at -4: 15 fall (60%, floor 70%) -> flagged
    rises = range(326, 345)  # 19 at +5: none rise (0%) but under 20 predictions -> not flagged
    likely = range(345, 365)  # 20 at +4: 14 rise (70%, the floor itself) -> not flagged
    codes: dict[int, Codes] = {
        **{i: (-4, 0, 0) for i in falls},
        **{i: (5, 0, 0) for i in rises},
        **{i: (4, 0, 0) for i in likely},
    }
    bot.fpl.respond("bootstrap-static/", bootstrap(codes=codes, extra=64))
    await bot.active_member(user_id=2001, team_id=1001)
    bot.fpl.respond(
        "stats/price-changes/",
        price_changes(
            *((i, THURSDAY, 45, 44) for i in list(falls)[:15]),
            *((i, THURSDAY, 45, 46) for i in list(likely)[:14]),
        ),
    )

    await run_night_directly(bot, THURSDAY)
    await advance_to(bot, uk(FRIDAY, 9))
    await bot.owner.send("/accuracy")
    flagged = bot.owner.last_reply
    await advance_to(bot, uk(FRIDAY + timedelta(days=14), 9))  # Thursday leaves the window
    await bot.owner.send("/accuracy")
    two_weeks_later = bot.owner.last_reply

    assert flagged.endswith(
        "\n\nBelow floor: tonight's -4 at 15/25 60% (floor 70%).\n"
        "Raise the alert threshold by hand if it persists; nothing changes by itself."
    )
    assert "+5  0/19 0% · 0/19 0%" in flagged
    assert "+4  14/20 70% · 14/20 70%" in flagged
    assert "-4  no data · 15/25 60%" in two_weeks_later  # still in the season total
    assert two_weeks_later.endswith("all met.")


async def test_the_floor_flag_covers_tomorrow_nights_codes_too(bot: BotHarness) -> None:
    very_likely = range(301, 321)  # 20 at -5 for tomorrow night: 16 fall Friday (80% < 85%)
    bot.fpl.respond(
        "bootstrap-static/",
        bootstrap(codes={i: (0, -5, 0) for i in very_likely}, extra=20),
    )
    await bot.active_member(user_id=2001, team_id=1001)
    bot.fpl.respond(
        "stats/price-changes/",
        price_changes(*((i, FRIDAY, 45, 44) for i in list(very_likely)[:16])),
    )

    await run_night_directly(bot, THURSDAY)
    await run_night_directly(bot, FRIDAY)
    await bot.owner.send("/accuracy")

    assert "Below floor: tomorrow night's -5 at 16/20 80% (floor 85%)." in bot.owner.last_reply
