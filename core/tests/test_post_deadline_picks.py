"""Ticket 31: the post-deadline picks job, the scheduler and startup catch-up.

The default clock is Thursday 19 Nov 2026 18:00 UTC, after the GW10 deadline. GW11's deadline is
Sat 21 Nov 11:00 UTC; the post-deadline job starts 5 minutes later. ``bot.start_scheduling()``
starts the bot's scheduled jobs (production starts them with the bot), and ``bot.advance`` lets
them run as simulated time passes.
"""

import json
from datetime import datetime, timedelta

from fplbot.sources.fpl import FplResponse
from tests.harness import FPL_FIXTURES, BotHarness, canned_fpl_response, fpl_fixture

GW11_DEADLINE = datetime.fromisoformat("2026-11-21T11:00:00Z")
JOB_START = GW11_DEADLINE + timedelta(minutes=5)
# Long enough for the startup refresh and catch-up (a few rate-limited requests) to finish.
STARTUP_TIME = timedelta(minutes=1)


STRIKEWELL, PASSMORE = 212, 208


def picks_for_1001(gameweek: int, captain: int) -> FplResponse:
    """Team 1001's Squad at a later deadline: the GW10 one with the armband moved."""
    data = json.loads((FPL_FIXTURES / "entry/1001/event/10/picks.json").read_text())
    data["entry_history"]["event"] = gameweek
    for pick in data["picks"]:
        pick["is_captain"] = pick["element"] == captain
        pick["multiplier"] = 2 if pick["element"] == captain else 1 if pick["position"] <= 11 else 0
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


def gw11_picks_for_1001() -> FplResponse:
    return picks_for_1001(11, captain=STRIKEWELL)


async def advance_to(bot: BotHarness, moment: datetime) -> None:
    await bot.advance(moment - bot.clock.now())


async def test_after_the_deadline_squad_shows_the_new_gameweek_without_member_action(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    bot.fpl.respond("entry/1001/event/11/picks/", gw11_picks_for_1001())
    await bot.start_scheduling()

    await advance_to(bot, JOB_START + timedelta(minutes=10))
    await alice.send("/squad")

    assert alice.last_reply == (
        "Alex's Aces · your Squad at the GW11 deadline\n"
        "GKP  Gatekeep\n"
        "DEF  Backline, Wallace, Blockley, Tackleton\n"
        "MID  Fakesson, Passmore, Dribbleton (VC), Crossley\n"
        "FWD  Placeholder, Strikewell (C)\n"
        "Bench: Benchwood, Sparesby, Reservo, Lastpick\n"
        "\n"
        "FPL hides GW12 picks until the deadline (Sat 28 Nov 11:00 your time), so changes "
        "you've made since GW11 don't show yet."
    )


async def test_while_fpl_is_updating_the_job_waits_and_probes_again_then_completes(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.start_scheduling()
    await bot.advance(STARTUP_TIME)
    updating = canned_fpl_response("503-updating")
    bot.fpl.respond("event-status/", updating, updating, updating, fpl_fixture("event-status/"))
    bot.fpl.respond("entry/1001/event/11/picks/", gw11_picks_for_1001())

    await advance_to(bot, JOB_START + timedelta(hours=1))
    await alice.send("/squad")

    probes = [r.at for r in bot.fpl.requests if r.path == "event-status" and r.at > GW11_DEADLINE]
    assert [p - JOB_START for p in probes] == [timedelta(minutes=m) for m in (0, 10, 20, 30)]
    picks = [r.at for r in bot.fpl.requests if r.path == "entry/1001/event/11/picks"]
    assert len(picks) == 1
    assert picks[0] > probes[-1]
    assert "your Squad at the GW11 deadline" in alice.last_reply
    assert not any("picks job" in reply for reply in bot.owner.replies)


async def test_re_running_the_job_for_a_completed_gameweek_changes_and_sends_nothing(
    bot: BotHarness,
) -> None:
    await bot.active_member(user_id=2001, team_id=1001)
    bot.fpl.respond("entry/1001/event/11/picks/", gw11_picks_for_1001())
    await bot.start_scheduling()
    await advance_to(bot, JOB_START + timedelta(minutes=10))
    stored = await bot.database_text()
    sent, requested = len(bot.telegram.calls), len(bot.fpl.requests)

    await bot.restart()  # startup catch-up finds GW10 and GW11 complete
    await bot.advance(timedelta(hours=1))
    succeeded = await bot.run_job("picks", bot.app.post_deadline.picks_job(11))

    later_paths = [r.path for r in bot.fpl.requests[requested:]]
    assert succeeded
    assert await bot.database_text() == stored
    assert [call for call in bot.telegram.calls[sent:] if call.method == "sendMessage"] == []
    assert not [path for path in later_paths if "picks" in path or path == "event-status"]


async def test_starting_after_missed_deadlines_catches_up_the_current_and_previous_gameweek(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(timedelta(minutes=1))  # join backfill: GW9 and GW10
    bot.fpl.respond("entry/1001/event/11/picks/", picks_for_1001(11, captain=STRIKEWELL))
    bot.fpl.respond("entry/1001/event/12/picks/", picks_for_1001(12, captain=PASSMORE))
    # The bot is down over the GW11 and GW12 deadlines (Sat 21 and Sat 28 Nov, 11:00 UTC).
    await advance_to(bot, datetime.fromisoformat("2026-11-28T15:00:00Z"))

    await bot.start_scheduling()
    await bot.advance(STARTUP_TIME)
    await alice.send("/squad")

    assert "entry/1001/event/11/picks" in bot.fpl.requested_paths
    assert "member_picks: (1, '2026-27', 11, 11, 212, 2, True, False)" in (
        await bot.database_text()
    )
    assert alice.last_reply == (
        "Alex's Aces · your Squad at the GW12 deadline\n"
        "GKP  Gatekeep\n"
        "DEF  Backline, Wallace, Blockley, Tackleton\n"
        "MID  Fakesson, Passmore (C), Dribbleton (VC), Crossley\n"
        "FWD  Placeholder, Strikewell\n"
        "Bench: Benchwood, Sparesby, Reservo, Lastpick"
    )


async def test_bootstrap_static_is_refreshed_90_and_30_minutes_before_and_just_after_a_deadline(
    bot: BotHarness,
) -> None:
    # Without the news reads and price snapshots (ticket 37): they fetch bootstrap-static too.
    await bot.start_scheduling(price_history=False)
    await bot.advance(STARTUP_TIME)
    fetched_before = len(bot.fpl.requests)

    await advance_to(bot, JOB_START + timedelta(minutes=30))

    fetches = [r.at for r in bot.fpl.requests[fetched_before:] if r.path == "bootstrap-static"]
    assert fetches == [
        GW11_DEADLINE - timedelta(minutes=90),
        GW11_DEADLINE - timedelta(minutes=30),
        JOB_START + timedelta(seconds=1),  # right after the probe
    ]


async def test_a_403_pauses_the_job_until_its_next_run_and_tells_the_owner_once(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.start_scheduling()
    await bot.advance(STARTUP_TIME)
    bot.fpl.respond("entry/1001/event/11/picks/", canned_fpl_response("403-forbidden"))

    await advance_to(bot, JOB_START + timedelta(hours=12))

    tries = [r for r in bot.fpl.requests if r.path == "entry/1001/event/11/picks"]
    assert len(tries) == 1
    assert [r for r in bot.owner.replies if "FPL-403" in r] == [
        "FPL-403: the picks job failed. FPL refused access (403). Not retried; the job waits for "
        "its next run."
    ]

    # Its next run: the startup catch-up after a restart, with FPL answering again.
    bot.fpl.respond("entry/1001/event/11/picks/", gw11_picks_for_1001())
    await bot.restart()
    await bot.advance(STARTUP_TIME)
    await alice.send("/squad")

    assert "your Squad at the GW11 deadline" in alice.last_reply
