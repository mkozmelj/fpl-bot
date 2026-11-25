"""Ticket 40: season rollover. The bot never rolls over by itself.

The default clock is Thursday 19 Nov 2026 18:00 UTC, in the 2026-27 season (the shared
``bootstrap-static`` fixture: GW1 deadline Fri 14 Aug 2026). The 2027-28 game "opens" on
Tue 20 Jul 2027: ``new_season_bootstrap()`` is the fixture a year on, every Gameweek unplayed and
every Footballer with a new id.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fplbot.jobs.post_deadline import REFERENCE_JOB
from fplbot.sources.fpl import FplResponse
from fplbot.store.schema import Base
from fplbot.store.seasons import CLEARED_AT_ROLLOVER, KEPT_AT_ROLLOVER
from tests.harness import FPL_FIXTURES, BotHarness, Chat, SentMessage
from tests.test_rivals import script_nearest_office_rivals

SETTLE = timedelta(minutes=2)
SUMMER_2027 = datetime(2027, 7, 2, 12, 0, tzinfo=UTC)
NEW_GAME_OPENS = datetime(2027, 7, 20, 9, 0, tzinfo=UTC)
NEW_ID = 1000  # added to every Footballer id in the new season

PAUSED = (
    "A new FPL season is being set up, so this is paused for now. I'll message you when it's ready."
)
CHECKLIST_START = "New FPL season detected: 2027-28."
GOAL_PROMPT = "The 2027-28 FPL season is set up. Is your Goal still right for it?"
STALE_BUTTON = "That button is out of date. Send /help to see what you can do."
# Last season's data the rollover clears, and aggregates it keeps (under "2026-27").
CLEARED = (
    "rival_picks",
    "followed_leagues",
    "league_standings",
    "member_leagues",
    "member_picks",
    "member_gameweeks",
)
KEPT = ("gameweeks", "footballers", "fixtures", "footballer_gameweek_stats", "job_completions")


def new_season_bootstrap() -> FplResponse:
    data: dict[str, Any] = json.loads((FPL_FIXTURES / "bootstrap-static.json").read_text())
    for event in data["events"]:
        deadline = datetime.fromisoformat(event["deadline_time"]) + timedelta(weeks=52)
        event["deadline_time"] = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
        event.update(
            finished=False,
            data_checked=False,
            is_previous=False,
            is_current=False,
            is_next=event["id"] == 1,
        )
    for element in data["elements"]:
        element["id"] += NEW_ID
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


async def advance_to(bot: BotHarness, moment: datetime) -> None:
    await bot.advance(moment - bot.clock.now())


async def new_season_detected(bot: BotHarness) -> None:
    """Summer 2027: FPL's new game is open, and the bot's startup refresh reads it."""
    await advance_to(bot, NEW_GAME_OPENS)
    bot.fpl.respond("bootstrap-static/", new_season_bootstrap())
    await bot.start_scheduling(price_history=False)
    await bot.advance(SETTLE)


async def new_season_shows(bot: BotHarness) -> None:
    """FPL shows the new season at the bot's next scheduled reference refresh (clock kept)."""
    await bot.advance(SETTLE)  # joins' backfills read 2026-27 first
    bot.fpl.respond("bootstrap-static/", new_season_bootstrap())
    await bot.run_job(REFERENCE_JOB, bot.app.post_deadline.refresh_job())


async def rolled_over(bot: BotHarness) -> SentMessage:
    """The owner's confirmed /rollover; returns the confirmation question."""
    await bot.owner.send("/rollover")
    asked = bot.owner.last_message
    await bot.owner.press("Roll over to 2027-28")
    await bot.advance(SETTLE)
    return asked


def checklists(owner: Chat) -> list[str]:
    return [text for text in owner.replies if text.startswith(CHECKLIST_START)]


def goal_prompts(member: Chat) -> list[SentMessage]:
    return [m for m in member.messages if m.text.startswith(GOAL_PROMPT)]


def rows(dump: str, table: str, season: str | None = None) -> list[str]:
    """``table``'s rows in ``bot.database_text()``, only ``season``'s if given."""
    return [
        line
        for line in dump.splitlines()
        if line.startswith(f"{table}: ") and (season is None or f"'{season}'" in line)
    ]


async def test_the_season_does_not_change_with_the_calendar(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await alice.send("/watch add Strikewell")

    await advance_to(bot, SUMMER_2027)  # FPL still shows 2026-27
    await alice.send("/watch")

    assert "Strikewell" in alice.last_reply


async def test_a_new_season_pauses_alerts_and_advice_and_dms_the_owner_a_checklist_once(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await alice.send("/watch add Strikewell")
    await bot.advance(SETTLE)
    told_alice, told_owner = len(alice.messages), len(bot.owner.messages)

    await new_season_detected(bot)
    await bot.advance(timedelta(days=1))  # past alice's 20:00 Price-alert time
    await bot.restart()
    await bot.advance(timedelta(hours=1))

    assert len(alice.messages) == told_alice
    # One checklist, and no job-failure DMs about the paused jobs.
    assert bot.owner.replies[told_owner:] == checklists(bot.owner)
    assert len(checklists(bot.owner)) == 1
    for command in ("/squad", "/league", "/rivals", "/gap", "/gap captain", "/watch"):
        await alice.send(command)
        assert alice.last_reply == PAUSED, command
    await alice.send("/time 19:30")
    assert alice.last_reply.startswith("Done. Price alerts at 19:30")


async def test_only_the_owner_can_roll_over_and_only_after_confirming(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    stranger = bot.private_chat(9999)
    await new_season_detected(bot)

    await stranger.send("/rollover")
    await alice.send("/rollover")
    await bot.owner.send("/rollover")
    asked = bot.owner.last_message
    await bot.owner.press("Cancel")
    await alice.send("/squad")

    assert stranger.replies == []
    assert alice.replies[-2] == "I don't know that command. /help shows what I can do."
    assert asked.text == (
        "Roll over to the 2027-28 season?\n"
        "Kept: Members (team ID, chat, timezone, alert time) and the 2026-27 aggregates, under "
        "their season.\n"
        "Cleared: Rival picks, Followed leagues, and Member and Rival history.\n"
        "Then each Member is asked once to reconfirm their Goal and league."
    )
    assert asked.buttons == ["Roll over to 2027-28", "Cancel"]
    assert bot.owner.last_reply == "Okay, no rollover. Send /rollover when you're ready."
    assert alice.last_reply == PAUSED


async def test_rollover_keeps_members_and_aggregates_and_clears_rival_data_and_history(
    bot: BotHarness,
) -> None:
    script_nearest_office_rivals(bot)
    alice = await bot.active_member(user_id=2001, team_id=1001)
    bob = await bot.active_member(user_id=2002, team_id=1002)
    await bot.start_scheduling(price_history=False)  # catch-up: GW9/10 picks, stats, gw-final
    await bot.advance(SETTLE)
    before = await bot.database_text()
    await new_season_shows(bot)

    await rolled_over(bot)
    after = await bot.database_text()

    assert bot.owner.last_reply == (
        "Season 2027-28 started. 2026-27 aggregates are kept under 2026-27. "
        "Asked 2 Members to reconfirm their Goal."
    )
    assert len(rows(after, "members")) == 2
    for table in CLEARED:
        assert rows(before, table, "2026-27"), table
        assert not rows(after, table, "2026-27"), table
    for table in KEPT:
        assert rows(after, table, "2026-27") == rows(before, table, "2026-27"), table
    assert rows(after, "gameweeks", "2027-28")  # the new season's reference data is read
    for member in (alice, bob):
        [prompt] = goal_prompts(member)
        assert prompt.buttons == ["Overall rank", "Mini-league"]


async def test_after_rollover_members_reconfirm_their_goal_and_advice_is_back(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await new_season_shows(bot)
    await rolled_over(bot)

    await alice.press("Mini-league")
    await alice.press("Office League")
    saved = alice.last_reply
    await alice.send("/squad")

    assert saved.startswith("Saved.")
    assert "Goal: Mini-league: Office League" in saved
    assert alice.last_reply != PAUSED


async def test_rolling_over_twice_does_nothing_the_second_time(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await new_season_shows(bot)
    asked = await rolled_over(bot)
    told_alice = len(alice.messages)
    before = await bot.database_text()

    await bot.owner.send("/rollover")
    nothing_waiting = bot.owner.last_reply
    await bot.owner.press("Roll over to 2027-28", on=asked)
    await bot.restart()
    await new_season_shows(bot)  # FPL still shows 2027-28: nothing new
    await bot.advance(SETTLE)

    assert nothing_waiting == "No new season to roll over to: 2027-28 is the current season."
    assert bot.owner.last_reply == STALE_BUTTON
    assert len(alice.messages) == told_alice
    assert len(checklists(bot.owner)) == 1
    assert rows(await bot.database_text(), "seasons") == rows(before, "seasons")


def test_every_table_is_either_cleared_or_kept_at_rollover() -> None:
    cleared = {model.__tablename__ for model in CLEARED_AT_ROLLOVER}
    kept = {model.__tablename__ for model in KEPT_AT_ROLLOVER}

    assert not cleared & kept
    assert cleared | kept == set(Base.metadata.tables)
