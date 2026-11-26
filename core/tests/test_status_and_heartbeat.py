"""Ticket 38: the owner's /status, the heartbeat ping and the ``ready sha=`` startup line.

The default clock is Thursday 19 Nov 2026 18:00 UTC, after the GW10 deadline (see
test_post_deadline_picks for the schedule).
"""

import re
from dataclasses import replace
from datetime import timedelta

from fplbot.config import Config
from tests.harness import DEPLOY_SHA, BotHarness

HEARTBEAT_URL = "https://monitor.example.test/ping/check-1"

STARTUP_TIME = timedelta(minutes=1)


async def test_owner_status_shows_uptime_version_completions_and_neon(bot: BotHarness) -> None:
    await bot.start_scheduling()
    # The startup catch-up stores GW9 and GW10 (picks, gw_final) and archives last night's Price
    # changes.
    await bot.advance(timedelta(hours=2, minutes=5))

    await bot.owner.send("/status")

    status = bot.owner.last_reply
    lines = status.splitlines()
    assert lines[:7] == [
        "Status",
        "Up 2 h 5 min · v0.1.0 (0123abc)",
        "Last completed:",
        "• price_archive: 2026-11-18, 19 Nov 18:00 UTC",
        "• picks: gw10, 19 Nov 18:00 UTC",
        "• elite: never",
        "• gw_final: gw10, 19 Nov 18:00 UTC",
    ]
    assert lines[7] == "Neon: reachable"
    assert re.fullmatch(r"Database size: \d+(\.\d)? MB of 1024 MB \(\d+%\)", lines[8]), lines[8]
    assert lines[9:] == [
        "Compute hours: not readable without a Neon API key; see the Neon console.",
    ]


async def test_status_from_anyone_but_the_owner_shows_nothing(bot: BotHarness) -> None:
    member = await bot.active_member(user_id=2001, team_id=1001)
    stranger = bot.private_chat(3001)

    await member.send("/status")
    await stranger.send("/status")

    assert member.last_reply == "I don't know that command. /help shows what I can do."
    assert stranger.replies == []


async def test_with_a_heartbeat_url_the_bot_pings_it_every_5_minutes(bot: BotHarness) -> None:
    await bot.restart(config=replace(bot.config, heartbeat_url=HEARTBEAT_URL))
    started = bot.clock.now()
    await bot.start_scheduling()

    await bot.advance(timedelta(minutes=16))

    assert bot.heartbeat.pings == [
        (started + timedelta(minutes=minutes), HEARTBEAT_URL) for minutes in (0, 5, 10, 15)
    ]


async def test_pings_stop_when_the_scheduler_stops(bot: BotHarness) -> None:
    await bot.restart(config=replace(bot.config, heartbeat_url=HEARTBEAT_URL))
    await bot.start_scheduling()
    await bot.advance(timedelta(minutes=6))
    pinged = len(bot.heartbeat.pings)

    await bot.app.scheduler.stop()
    await bot.advance(timedelta(minutes=30))

    assert pinged == 2
    assert len(bot.heartbeat.pings) == pinged


async def test_without_a_heartbeat_url_nothing_is_pinged(bot: BotHarness) -> None:
    await bot.start_scheduling()

    await bot.advance(timedelta(minutes=30))

    assert bot.heartbeat.pings == []


async def test_startup_logs_ready_with_the_commit_and_tells_the_owner_online(
    bot: BotHarness,
) -> None:
    await bot.start_up()
    await bot.advance(timedelta(hours=1))
    first_process = [line for line in bot.logs if "ready sha=" in line]

    await bot.restart()

    assert first_process == [f"fplbot.app ready sha={DEPLOY_SHA}"]
    assert [line for line in bot.logs if "ready sha=" in line] == [
        f"fplbot.app ready sha={DEPLOY_SHA}"
    ] * 2
    assert bot.owner.replies == ["online v0.1.0 (0123abc)"] * 2
    assert any(call.method == "getUpdates" for call in bot.telegram.calls)


async def test_a_railway_build_logs_the_commit_railway_deployed(bot: BotHarness) -> None:
    # Railway builds from GitHub (ADR 0004): the image's GIT_SHA build argument is left empty, and
    # Railway sets RAILWAY_GIT_COMMIT_SHA at runtime.
    railway_sha = "fedcba9876543210fedcba9876543210fedcba98"
    config = Config.from_env(
        {
            "TELEGRAM_BOT_TOKEN": bot.config.telegram_bot_token,
            "DATABASE_URL": bot.config.database_url,
            "OWNER_TELEGRAM_ID": str(bot.config.owner_telegram_id),
            "FPL_SOURCE": "fake",
            "GIT_SHA": "",
            "RAILWAY_GIT_COMMIT_SHA": railway_sha,
        }
    )

    await bot.start_up()
    await bot.restart(config=config)

    assert [line for line in bot.logs if "ready sha=" in line][-1] == (
        f"fplbot.app ready sha={railway_sha}"
    )
    assert bot.owner.replies[-1] == "online v0.1.0 (fedcba9)"


def storage_warnings(bot: BotHarness) -> list[str]:
    return [reply for reply in bot.owner.replies if reply.startswith("Neon storage is at")]


async def test_the_owner_is_told_once_when_database_storage_passes_70_percent(
    bot: BotHarness,
) -> None:
    # The test database is a few MB, so a 1 MB limit puts it far past 70%.
    await bot.restart(config=replace(bot.config, database_storage_limit_mb=1))
    await bot.start_scheduling()

    await bot.advance(timedelta(hours=12))  # the daily check runs at 04:30 UK (Fri)
    told = storage_warnings(bot)
    await bot.restart()
    await bot.advance(timedelta(days=1))  # and again on Saturday

    assert len(told) == 1
    assert re.fullmatch(
        r"Neon storage is at \d+% \(\d+\.\d MB of 1 MB\)\. Check which tables grew before the "
        r"next Gameweek \(docs/runbook-secrets\.md, Monthly Neon check\)\.",
        told[0],
    ), told[0]
    assert storage_warnings(bot) == told


async def test_below_70_percent_storage_the_owner_is_not_told(bot: BotHarness) -> None:
    await bot.start_scheduling()

    await bot.advance(timedelta(hours=12))

    assert storage_warnings(bot) == []
