"""Ticket 36: the nightly Price alert.

Team 1001's Squad at the GW10 deadline (the shared fixtures) owns Footballers 102-103 and
201-213; Testkeeper (101) is not owned, so he goes on Watch lists. Price projections are added to
the shared ``bootstrap-static`` per test (synthetic likelihood codes, -5..+5, for tonight,
tomorrow night and the night after). The default clock is Thursday 19 Nov 2026, 18:00 UK (GMT);
the GW11 deadline is Saturday 21 Nov, 11:00 UK.

The bot's scheduler runs the alerts: every test here starts scheduling first (and lets the
startup refresh finish before it scripts FPL answers), then lets simulated time pass through the
night's send window.
"""

import json
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from fplbot.sources.fpl import FplResponse
from tests.harness import BotHarness, Chat, canned_fpl_response, fpl_fixture

UK = ZoneInfo("Europe/London")
THURSDAY = date(2026, 11, 19)
FRIDAY = date(2026, 11, 20)  # the night before the GW11 deadline
BACKFILL_TIME = timedelta(minutes=1)
STARTUP_TIME = timedelta(minutes=1)
# After the last possible send time (23:15 UK) and its 10-minute retry window.
NIGHT_OVER = time(23, 30)


@pytest.fixture(autouse=True)
async def scheduling(bot: BotHarness) -> None:
    # Without the news reads and price snapshots (ticket 37): they fetch bootstrap-static too.
    await bot.start_scheduling(price_history=False)
    await bot.advance(STARTUP_TIME)


type Codes = tuple[int, int] | tuple[int, int, int]


def bootstrap(
    codes: dict[int, Codes],
    *,
    statuses: dict[int, str] | None = None,
    calibrating: bool = False,
    with_projections: bool = True,
) -> FplResponse:
    """The shared ``bootstrap-static`` with price-change fields: ``codes`` maps a Footballer id
    to his likelihood codes (tonight, tomorrow[, night after]); everyone else is 0."""
    data: dict[str, Any] = json.loads(fpl_fixture("bootstrap-static/").body)
    for element in data["elements"]:
        element["status"] = (statuses or {}).get(element["id"], element.get("status", "a"))
        if not with_projections:
            continue
        nights = (*codes.get(element["id"], (0, 0)), 0)[:3]
        element["price_change_percent"] = "0.0"
        element["price_change_calibrating"] = calibrating
        element["price_change_projections"] = [
            {"offset": offset, "projected_percent": str(code * 20.0), "likelihood": code}
            for offset, code in enumerate(nights)
        ]
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


async def ljubljana_member(bot: BotHarness, user_id: int = 2001, team_id: int = 1001) -> Chat:
    member = await bot.invited_friend(user_id)
    await member.send(str(team_id))
    await member.press("Yes, that's me")
    await member.press("Overall rank")
    await member.press("Other…")
    await member.send("Ljubljana")
    assert member.last_reply.startswith("You're all set"), member.last_reply
    return member


def uk_time(moment: datetime) -> str:
    return f"{moment.astimezone(UK):%a %H:%M}"


async def run_price_alerts(bot: BotHarness, night: date = THURSDAY) -> list[str]:
    """Let the UK night ``night`` pass until its send window is over; the UK times of its
    planned Price alerts."""
    runs = await bot.app.price_alerts.planned_runs(night)
    await bot.advance(datetime.combine(night, NIGHT_OVER, UK) - bot.clock.now())
    return [uk_time(run.at) for run in runs]


async def test_a_member_at_20_00_ljubljana_gets_the_alert_at_19_00_uk(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({103: (-5, 0)}))
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)
    before = len(alice.replies)

    sent_at = await run_price_alerts(bot)

    assert sent_at == ["Thu 19:00"]
    assert alice.replies[before:] == [
        "Price alert · GW11 · tonight 00:00 UK\n"
        "\n"
        "Likely to fall (you own)\n"
        "• Placeholder FWD SOU £6.5m → £6.4m · Very likely · doubtful\n"
        "\n"
        "If you were planning to sell anyway, doing it before 00:00 UK saves £0.1m."
    ]


async def test_content_ordering_flags_and_tomorrow_line(bot: BotHarness) -> None:
    bot.fpl.respond(
        "bootstrap-static/",
        bootstrap(
            {
                102: (-5, 0),  # Fakesson: Very likely to fall
                212: (-5, 0),  # Strikewell (injured): Very likely to fall
                210: (-4, -5),  # Crossley: Likely tonight, so not repeated tomorrow
                103: (-4, 0),  # Placeholder (doubtful): Likely to fall
                208: (-3, -5),  # Passmore: only tomorrow, Very likely
                213: (-3, -4),  # Lastpick: tomorrow but only Likely: not shown
                211: (0, 0, -5),  # Reservo: the night after: never shown
                209: (5, 5),  # Dribbleton: an owned rise: never shown
                101: (4, 0),  # Testkeeper (doubtful, watched): Likely to rise
            },
            statuses={212: "i", 101: "d"},
        ),
    )
    alice = await ljubljana_member(bot)
    await alice.send("/watch add testkeeper")
    await bot.advance(BACKFILL_TIME)

    await run_price_alerts(bot)

    assert alice.last_reply == (
        "Price alert · GW11 · tonight 00:00 UK\n"
        "\n"
        "Likely to fall (you own)\n"
        "• Fakesson MID NOR £8.0m → £7.9m · Very likely\n"
        "• Strikewell FWD EAS £11.0m → £10.9m · Very likely · injured\n"
        "• Crossley MID NOR £6.0m → £5.9m · Likely\n"
        "• Placeholder FWD SOU £6.5m → £6.4m · Likely · doubtful\n"
        "\n"
        "Likely to rise (Watch list)\n"
        "• Testkeeper GKP NOR £4.5m → £4.6m · Likely\n"
        "\n"
        "Tomorrow night (Very likely): Passmore to fall.\n"
        "If you were planning to sell or buy anyway, doing it before 00:00 UK saves £0.1m "
        "a Footballer."
    )


async def test_owned_rises_and_watch_list_falls_are_never_mentioned(bot: BotHarness) -> None:
    bot.fpl.respond(
        "bootstrap-static/",
        bootstrap({209: (5, 5), 102: (-5, -5), 101: (-5, -5)}),
    )
    owner_of_dribbleton = await ljubljana_member(bot, user_id=2001, team_id=1001)
    watcher = await ljubljana_member(bot, user_id=2003, team_id=1003)  # owns nobody
    await watcher.send("/watch add testkeeper")
    await watcher.send("/watch add fakesson")
    await bot.advance(BACKFILL_TIME)
    before = len(owner_of_dribbleton.replies), len(watcher.replies)

    await run_price_alerts(bot)

    # Alice owns Fakesson, so she hears about his fall; the watcher hears nothing.
    assert "Dribbleton" not in owner_of_dribbleton.last_reply
    assert len(owner_of_dribbleton.replies) == before[0] + 1
    assert len(watcher.replies) == before[1]


async def test_a_quiet_night_sends_nothing(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({101: (5, 5), 208: (-3, -5)}))
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)
    sent = len(bot.telegram.sent_messages)

    await run_price_alerts(bot)

    assert alice.last_reply.startswith("You're all set")
    assert len(bot.telegram.sent_messages) == sent


STALE_CAVEAT = "Based on your Squad at the last deadline. Ignore any you've already sold."


async def test_the_stale_squad_caveat_appears_the_night_before_a_deadline(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({102: (-5, 0)}))
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)

    await run_price_alerts(bot, THURSDAY)
    thursday = alice.last_reply
    await run_price_alerts(bot, FRIDAY)
    friday = alice.last_reply

    assert STALE_CAVEAT not in thursday
    assert friday == (
        "Price alert · GW11 · tonight 00:00 UK\n"
        "\n"
        "Likely to fall (you own)\n"
        "• Fakesson MID NOR £8.0m → £7.9m · Very likely\n"
        "\n"
        "If you were planning to sell anyway, doing it before 00:00 UK saves £0.1m.\n"
        f"{STALE_CAVEAT}"
    )


async def test_the_caveat_appears_when_only_an_older_squad_is_stored(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({102: (-5, 0)}))
    bot.fpl.respond("entry/1001/event/10/picks/", FplResponse(404, b"{}"))
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)

    await run_price_alerts(bot, THURSDAY)

    assert alice.last_reply.startswith("Price alert · GW11")
    assert alice.last_reply.endswith(STALE_CAVEAT)


async def test_calibrating_projections_send_nothing(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({102: (-5, -5)}, calibrating=True))
    await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)
    sent = len(bot.telegram.sent_messages)

    await run_price_alerts(bot)

    # Calibrating is FPL's normal early-season state, not an incident: the owner isn't told.
    assert len(bot.telegram.sent_messages) == sent


async def test_missing_projection_fields_send_members_nothing_and_tell_the_owner_once(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({}, with_projections=False))
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)
    before = len(alice.replies), len(bot.owner.replies)

    await run_price_alerts(bot)

    assert len(alice.replies) == before[0]
    assert bot.owner.replies[before[1] :] == [
        "FPL-BAD-DATA: the price-alert job failed. FPL answered without the fields we need. "
        "Tonight's Price alerts were not sent."
    ]


def bootstrap_requests(bot: BotHarness) -> list[str]:
    return [uk_time(r.at) for r in bot.fpl.requests if r.path == "bootstrap-static"]


async def test_unreachable_fpl_is_retried_once_then_the_owner_gets_one_dm(
    bot: BotHarness,
) -> None:
    alice = await ljubljana_member(bot)
    london = await bot.active_member(user_id=2002, team_id=1002, timezone="Europe/London")
    await london.send("/time 21:00")
    await bot.advance(BACKFILL_TIME)
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    before = len(alice.replies), len(london.replies), len(bot.owner.replies)
    fetched_before = len(bootstrap_requests(bot))

    sent_at = await run_price_alerts(bot)

    assert sent_at == ["Thu 19:00", "Thu 21:00"]
    # Each run: a fetch (5 tries with backoff), then one more 10 minutes later.
    fetches = bootstrap_requests(bot)[fetched_before:]
    assert len(fetches) == 20
    assert (fetches[0], fetches[5], fetches[10], fetches[15]) == (
        "Thu 19:00",
        "Thu 19:10",
        "Thu 21:00",
        "Thu 21:10",
    )
    assert (len(alice.replies), len(london.replies)) == before[:2]
    assert bot.owner.replies[before[2] :] == [
        "FPL-DOWN: the price-alert job failed. FPL kept failing (429/5xx) after 5 tries. "
        "Tonight's Price alerts were not sent."
    ]


async def test_a_fetch_that_recovers_within_10_minutes_still_sends_the_alert(
    bot: BotHarness,
) -> None:
    alice = await ljubljana_member(bot)
    await bot.advance(BACKFILL_TIME)
    bot.fpl.respond(
        "bootstrap-static/",
        *[canned_fpl_response("502-bad-gateway")] * 5,
        bootstrap({102: (-5, 0)}),
    )
    owner_dms = len(bot.owner.replies)

    await run_price_alerts(bot)

    assert alice.last_reply.startswith("Price alert · GW11")
    assert len(bot.owner.replies) == owner_dms


async def test_no_retry_after_the_23_15_cut_off(bot: BotHarness) -> None:
    late = await bot.active_member(user_id=2002, team_id=1001, timezone="Europe/London")
    await late.send("/time 23:15")
    await bot.advance(BACKFILL_TIME)
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    fetched_before = len(bootstrap_requests(bot))

    await run_price_alerts(bot)

    assert len(bootstrap_requests(bot)[fetched_before:]) == 5  # one fetch, no retry
    assert bot.owner.last_reply.startswith("FPL-DOWN: the price-alert job failed.")


async def test_members_sharing_a_send_time_share_one_fetch(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({102: (-5, 0), 101: (5, 0)}))
    alice = await ljubljana_member(bot, user_id=2001, team_id=1001)
    bob = await bot.active_member(user_id=2003, team_id=1003, timezone="Europe/Paris")
    await bob.send("/watch add testkeeper")
    await bot.advance(BACKFILL_TIME)
    fetched_before = len(bootstrap_requests(bot))

    sent_at = await run_price_alerts(bot)

    assert sent_at == ["Thu 19:00"]  # 20:00 in Ljubljana and in Paris
    assert bootstrap_requests(bot)[fetched_before:] == ["Thu 19:00"]
    assert "Fakesson" in alice.last_reply
    assert "Testkeeper" in bob.last_reply


async def test_send_times_outside_17_00_to_23_15_uk_are_clamped(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({103: (-5, 0)}))
    priya = await bot.active_member(user_id=2001, team_id=1001, timezone="Asia/Kolkata")
    late = await bot.active_member(user_id=2002, team_id=1002, timezone="Europe/London")
    await late.send("/time 23:45")
    await bot.advance(BACKFILL_TIME)
    before = len(priya.replies)

    sent_at = await run_price_alerts(bot, FRIDAY)

    # 20:00 in Kolkata is 14:30 UK: clamped to 17:00 UK. 23:45 UK is clamped to 23:15.
    assert sent_at == ["Fri 17:00", "Fri 23:15"]
    assert [reply.splitlines()[0] for reply in priya.replies[before:]] == [
        "Price alert · GW11 · tonight 00:00 UK"
    ]


async def test_a_new_alert_time_counts_from_tonight(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({103: (-5, 0)}))
    alice = await ljubljana_member(bot)  # 20:00 Ljubljana: 19:00 UK
    await bot.advance(datetime(2026, 11, 19, 18, 30, tzinfo=UK) - bot.clock.now())

    await alice.send("/time 19:45")  # 18:45 UK
    await bot.advance(datetime(2026, 11, 19, 18, 50, tzinfo=UK) - bot.clock.now())

    assert alice.last_reply.startswith("Price alert · GW11 · tonight 00:00 UK")


async def test_a_restart_just_after_a_send_time_does_not_send_the_alert_again(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", bootstrap({103: (-5, 0)}))
    alice = await ljubljana_member(bot)  # 20:00 Ljubljana: 19:00 UK
    await bot.advance(datetime(2026, 11, 19, 19, 2, tzinfo=UK) - bot.clock.now())
    sent = len(alice.replies)

    await bot.restart()  # inside the run's grace window: the scheduler fires it again
    await bot.advance(datetime(2026, 11, 19, 19, 30, tzinfo=UK) - bot.clock.now())

    assert alice.replies[sent - 1].startswith("Price alert · GW11")
    assert len(alice.replies) == sent
