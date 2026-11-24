"""Ticket 28: joining (team ID, Goal, timezone), settings and ``/leave``.

Mirrors the walkthroughs of the approved join-flow prototype (ticket 14): happy path, wrong team
ID, same team twice, button tapped twice, no mini-league, typed timezone, leaving, abandoned
setup.
"""

from datetime import timedelta

from fplbot.sources.fpl import FplResponse
from tests.harness import BotHarness, start_code_in

ASK_TEAM_ID = (
    "Send me your FPL team ID.\n"
    "You can find it in the address bar on the FPL site, in the number after /entry/ "
    "(open the Points tab)."
)
ASK_GOAL = (
    "What should my advice aim for?\n"
    "• Overall rank (the default)\n"
    "• Mini-league: stay ahead of the Rivals in one league\n"
    "You can switch any time with /goal."
)
ASK_TZ = (
    "Which timezone are you in? Your nightly Price alert goes out at 20:00 your time "
    "(change it with /time)."
)
TZ_BUTTONS = ["Europe/London", "Europe/Paris", "America/New_York", "Asia/Kolkata"]
HELP = (
    "/squad  your Squad at the last deadline\n"
    "/league  your league table\n"
    "/rivals  where your Squad differs from your nearest Rivals\n"
    "/rivals all\n"
    "/watch  show your Watch list\n"
    "/watch add <name>\n"
    "/watch remove <name>\n"
    "/goal  switch Goal\n"
    "/time HH:MM  Price alert time\n"
    "/tz  change timezone\n"
    "/settings  show everything I know about you\n"
    "/leave  delete your data and leave"
)
STALE = "That button is out of date. Send /help to see what you can do."
FINISH_FIRST = "Let's finish setting you up first."


def settings(team: str, goal: str, timezone: str, alert: str = "20:00") -> str:
    return (
        f"Team: {team}\n"
        f"Goal: {goal}\n"
        f"Timezone: {timezone}\n"
        f"Price alert: {alert} your time, only on nights with something to report"
    )


async def test_a_new_member_is_asked_for_their_team_id_and_shown_the_team_to_confirm(
    bot: BotHarness,
) -> None:
    alice = await bot.invited_friend(user_id=2001)
    assert alice.last_reply == ASK_TEAM_ID

    await alice.send("1001")

    assert alice.last_reply == (
        'Found "Alex\'s Aces", managed by Alex K., overall rank 84,213.\nIs that you?'
    )
    assert alice.last_message.buttons == ["Yes, that's me", "No, wrong team"]


async def test_happy_path_links_team_picks_mini_league_and_timezone(bot: BotHarness) -> None:
    alice = await bot.invited_friend(user_id=2001)
    await alice.send("1001")

    await alice.press("Yes, that's me")
    assert alice.last_reply == ASK_GOAL
    assert alice.last_message.buttons == ["Overall rank", "Mini-league"]

    await alice.press("Mini-league")
    assert alice.last_reply == "Which mini-league?"
    assert alice.last_message.buttons == ["Office League", "Sunday Pub XI", "Cup Rivals H2H"]

    await alice.press("Office League")
    assert alice.last_reply == ASK_TZ
    assert alice.last_message.buttons == [*TZ_BUTTONS, "Other…"]

    await alice.press("Europe/London")
    assert alice.last_reply == (
        "You're all set, Alex's Aces.\n\n"
        + settings("Alex's Aces (ID 1001)", "Mini-league: Office League", "Europe/London")
        + f"\n\nCommands:\n{HELP}"
    )


async def test_wrong_team_id_is_corrected(bot: BotHarness) -> None:
    alice = await bot.invited_friend(user_id=2001)

    await alice.send("my id")
    await alice.send("9999")
    await alice.send("1002")
    await alice.press("No, wrong team")
    await alice.send("1001")
    await alice.press("Yes, that's me")

    assert alice.replies[2:] == [
        "That doesn't look like a team ID. It's just digits, like 1234567.",
        "I couldn't find an FPL team with ID 9999. Check the number and send it again.",
        'Found "Bojan United", managed by Bojan M., overall rank 412,889.\nIs that you?',
        "No problem. Send the correct team ID.",
        'Found "Alex\'s Aces", managed by Alex K., overall rank 84,213.\nIs that you?',
        ASK_GOAL,
    ]


async def test_a_team_linked_to_another_member_is_refused(bot: BotHarness) -> None:
    await bot.active_member(user_id=2001, team_id=1001)
    bob = await bot.invited_friend(user_id=2002)

    await bob.send("1001")
    refusal = bob.last_reply
    await bob.send("1002")

    assert refusal == (
        "That team is already linked to another Member. If that is a mistake, ask the owner."
    )
    assert bob.last_reply.startswith('Found "Bojan United"')


async def test_a_team_linked_while_another_member_was_confirming_it_is_refused(
    bot: BotHarness,
) -> None:
    alice = await bot.invited_friend(user_id=2001)
    bob = await bot.invited_friend(user_id=2002)
    await alice.send("1001")
    await bob.send("1001")

    await alice.press("Yes, that's me")
    await bob.press("Yes, that's me")

    assert alice.last_reply == ASK_GOAL
    assert bob.last_reply == (
        "That team is already linked to another Member. If that is a mistake, ask the owner."
    )


async def test_a_button_tapped_twice_or_after_a_command_changes_nothing(bot: BotHarness) -> None:
    alice = await bot.invited_friend(user_id=2001)
    await alice.send("1001")
    confirmation = alice.last_message

    await alice.press("Yes, that's me", on=confirmation)
    goal_question = alice.last_message
    await alice.press("Yes, that's me", on=confirmation)
    await alice.send("/help")
    await alice.press("Overall rank", on=goal_question)

    assert alice.replies[-5:] == [ASK_GOAL, STALE, FINISH_FIRST, ASK_GOAL, STALE]
    # The re-asked question still works, and the Goal was not set by the stale tap.
    await alice.press("Mini-league")
    assert alice.last_reply == "Which mini-league?"


async def test_without_a_mini_league_the_goal_falls_back_to_overall_rank(
    bot: BotHarness,
) -> None:
    clara = await bot.invited_friend(user_id=2003)
    await clara.send("1003")
    await clara.press("Yes, that's me")

    await clara.press("Mini-league")
    fallback = clara.replies[-2:]
    await clara.press("Asia/Kolkata")
    await clara.send("/goal")

    assert fallback == [
        "You're not in any private mini-league yet, so I've set your Goal to Overall rank. "
        "Switch with /goal once you join one.",
        ASK_TZ,
    ]
    assert "Goal: Overall rank" in clara.replies[-2]
    assert clara.last_reply == ASK_GOAL


async def test_a_typed_timezone_and_alert_time(bot: BotHarness) -> None:
    alice = await bot.invited_friend(user_id=2001)
    await alice.send("1001")
    await alice.press("Yes, that's me")
    await alice.press("Overall rank")

    await alice.press("Other…")
    await alice.send("Atlantis")
    await alice.send("Ljubljana")
    joined = list(alice.replies[-3:])
    await alice.send("/time 19:30")
    await alice.send("/time 25:00")
    await alice.send("/settings")

    assert joined[0] == "Type your city or timezone (for example Ljubljana or Europe/Berlin)."
    assert joined[1] == (
        'I don\'t know "Atlantis". Try a city (Ljubljana, Sydney…) '
        "or a zone name like Europe/Berlin."
    )
    assert "Timezone: Europe/Ljubljana" in joined[2]
    assert alice.replies[-3:] == [
        "Done. Price alerts at 19:30 Europe/Ljubljana time.",
        "Use 24-hour time, like /time 19:30.",
        settings("Alex's Aces (ID 1001)", "Overall rank", "Europe/Ljubljana", alert="19:30")
        + "\nWatch list: empty",
    ]


async def test_zone_names_and_multi_word_cities_are_understood(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)

    await alice.send("/tz")
    await alice.press("Other…")
    await alice.send("america/argentina/buenos_aires")
    by_zone = alice.last_reply
    await alice.send("/tz")
    await alice.press("Other…")
    await alice.send("new york")

    assert "Timezone: America/Argentina/Buenos_Aires" in by_zone
    assert alice.last_reply.startswith("Saved.\n\n")
    assert "Timezone: America/New_York" in alice.last_reply


async def test_alert_time_outside_the_uk_window_states_the_real_send_time(
    bot: BotHarness,
) -> None:
    # The harness clock is 19 November: UK on GMT, Kolkata 5:30 ahead.
    priya = await bot.active_member(user_id=2004, team_id=1002, timezone="Asia/Kolkata")

    await priya.send("/time 20:00")
    early = priya.last_reply
    await priya.send("/time 23:00")
    inside = priya.last_reply
    await priya.send("/time 5:15")

    assert early == (
        "Done. Price alerts at 20:00 Asia/Kolkata time.\n"
        "Price alerts only go out between 17:00 and 23:15 UK time, so yours will arrive at "
        "17:00 UK (22:30 your time)."
    )
    assert inside == "Done. Price alerts at 23:00 Asia/Kolkata time."
    assert priya.last_reply == (
        "Done. Price alerts at 05:15 Asia/Kolkata time.\n"
        "Price alerts only go out between 17:00 and 23:15 UK time, so yours will arrive at "
        "23:15 UK (04:45 your time)."
    )


async def test_settings_goal_and_timezone_for_an_active_member(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)

    await alice.send("/help")
    help_reply = alice.last_reply
    await alice.send("/goal")
    await alice.press("Mini-league")
    await alice.press("Sunday Pub XI")
    switched = alice.last_reply
    await alice.send("/tz")
    await alice.press("Europe/Paris")
    await alice.send("/goal")
    await alice.press("Overall rank")

    assert help_reply == HELP
    assert switched == "Saved.\n\n" + settings(
        "Alex's Aces (ID 1001)", "Mini-league: Sunday Pub XI", "Europe/London"
    )
    assert alice.last_reply == "Saved.\n\n" + settings(
        "Alex's Aces (ID 1001)", "Overall rank", "Europe/Paris"
    )


async def test_a_command_abandons_the_open_question(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await alice.send("/tz")
    await alice.press("Other…")

    await alice.send("/settings")
    await alice.send("Ljubljana")
    await alice.send("/frobnicate")

    assert alice.replies[-2:] == [
        "I didn't catch that. /help shows what I can do.",
        "I don't know that command. /help shows what I can do.",
    ]
    await alice.send("/settings")
    assert "Timezone: Europe/London" in alice.last_reply


async def test_an_abandoned_setup_resumes_with_start(bot: BotHarness) -> None:
    bob = await bot.invited_friend(user_id=2002)
    await bob.send("1002")
    await bob.press("Yes, that's me")

    await bob.send("/settings")
    await bob.send("/start")

    assert bob.replies[-3:] == [FINISH_FIRST, ASK_GOAL, ASK_GOAL]
    await bob.press("Overall rank")
    await bob.press("Europe/London")
    assert bob.last_reply.startswith("You're all set, Bojan United.")
    await bob.send("/start")
    assert bob.last_reply == f"Welcome back, Bojan United.\n\n{HELP}"


async def test_setup_resumes_after_the_bot_forgets_the_open_question(bot: BotHarness) -> None:
    """Open questions are held in memory only; a restart must not strand a joining Member."""
    bob = await bot.invited_friend(user_id=2002)
    await bot.restart()
    await bob.send("1002")
    await bob.press("Yes, that's me")
    goal_question = bob.last_message
    await bot.restart()

    await bob.press("Overall rank", on=goal_question)
    stale = bob.last_reply
    await bob.send("hello")

    assert stale == STALE
    assert bob.last_reply == ASK_GOAL


async def test_fpl_being_unreachable_is_explained_and_the_id_can_be_resent(
    bot: BotHarness,
) -> None:
    alice = await bot.invited_friend(user_id=2001)
    bot.fpl.respond("entry/1001/", FplResponse(503, b"The game is being updated."))

    await alice.send("1001")
    unreachable = alice.last_reply
    bot.fpl.respond("entry/1001/")  # back to the fixture
    await alice.send("1001")

    assert unreachable == "I can't reach FPL right now. Try again in a few minutes."
    assert alice.last_reply.startswith('Found "Alex\'s Aces"')


async def test_leaving_deletes_the_member_and_the_code_cannot_rejoin(bot: BotHarness) -> None:
    await bot.owner.send("/invite")
    code = start_code_in(bot.owner.last_reply)
    alice = bot.private_chat(user_id=2001)
    await alice.send(f"/start {code}")
    await alice.send("1001")
    await alice.press("Yes, that's me")
    await alice.press("Overall rank")
    await alice.press("Europe/London")

    await alice.send("/leave")
    assert alice.last_reply == (
        "This deletes everything I store about you: your team ID, Goal, Watch list, timezone "
        "and chat ID. Your invite code cannot be reused. Continue?"
    )
    assert alice.last_message.buttons == ["Delete my data", "Keep me"]
    await alice.press("Delete my data")
    assert alice.last_reply == (
        "Done. Everything I stored about you is deleted. To rejoin you need a new invite."
    )

    # Only the used invite (no link to Alice) and Alembic's bookkeeping remain.
    stored = (await bot.database_text()).splitlines()
    assert {row.split(":")[0] for row in stored} == {"invites", "alembic_version"}
    assert not [row for row in stored if "Alex" in row]

    replies_after_leaving = len(alice.replies)
    await alice.send("/settings")
    await alice.send("1001")
    assert len(alice.replies) == replies_after_leaving  # a stranger again: silence
    await alice.send(f"/start {code}")
    assert alice.last_reply == (
        "That invite code has already been used. Ask the owner for a new one."
    )


async def test_keep_me_keeps_everything_and_a_new_invite_rejoins_after_leaving(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await alice.send("/leave")
    await alice.press("Keep me")
    kept = alice.last_reply
    await alice.send("/settings")
    still_there = alice.last_reply

    await alice.send("/leave")
    await alice.press("Delete my data")
    await bot.owner.send("/invite")
    await alice.send(f"/start {start_code_in(bot.owner.last_reply)}")
    await alice.send("1001")

    assert kept == "Okay, nothing deleted."
    assert still_there.startswith("Team: Alex's Aces (ID 1001)")
    assert alice.last_reply.startswith('Found "Alex\'s Aces"')


async def test_a_joining_member_can_leave(bot: BotHarness) -> None:
    bob = await bot.invited_friend(user_id=2002)

    await bob.send("/leave")
    await bob.press("Delete my data")

    assert bob.last_reply.startswith("Done. Everything I stored about you is deleted.")
    assert "members:" not in await bot.database_text()


async def test_buttons_after_leaving_get_silence(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await alice.send("/leave")
    leave_question = alice.last_message
    await alice.press("Delete my data")
    replies_after_leaving = len(alice.replies)

    await alice.press("Keep me", on=leave_question)

    assert len(alice.replies) == replies_after_leaving


async def test_logs_name_members_by_number_only_through_setup_and_leaving(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=7_654_321, team_id=1001)
    await alice.send("/leave")
    await alice.press("Delete my data")
    await bot.advance(timedelta(minutes=1))

    log_text = "\n".join(bot.logs)

    assert "member 1 finished setup" in log_text
    assert "member 1 left" in log_text
    for identifier in ["7654321", "1001", "Alex", "Kestrel"]:
        assert identifier not in log_text
