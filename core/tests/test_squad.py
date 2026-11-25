"""Ticket 30: ``/squad`` and the join backfill.

Linking a team starts a background backfill of the Member's season history and past picks
(it runs at routine priority, so tests let simulated time pass for it). ``/squad`` shows the
Squad as of the last deadline. The default clock is Thursday 19 Nov 2026, after the GW10
deadline and before GW11's (Sat 21 Nov, 11:00 UTC).
"""

from datetime import timedelta

from tests.harness import BotHarness, canned_fpl_response

BACKFILL_TIME = timedelta(minutes=1)


async def test_squad_shows_the_last_deadline_squad_with_captain_and_vice(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001, timezone="Asia/Kolkata")
    await bot.advance(BACKFILL_TIME)

    await alice.send("/squad")

    assert alice.last_reply == (
        "Alex's Aces · your Squad at the GW10 deadline\n"
        "GKP  Gatekeep\n"
        "DEF  Backline, Wallace, Blockley, Tackleton\n"
        "MID  Fakesson (C), Passmore, Dribbleton (VC), Crossley\n"
        "FWD  Placeholder, Strikewell\n"
        "Bench: Benchwood, Sparesby, Reservo, Lastpick\n"
        "\n"
        "FPL hides GW11 picks until the deadline (Sat 21 Nov 16:30 your time), so changes "
        "you've made since GW10 don't show yet."
    )


def tables_with_rows(database_text: str) -> set[str]:
    return {row.split(":")[0] for row in database_text.splitlines()}


async def test_history_and_picks_are_stored_on_join_and_deleted_on_leave(bot: BotHarness) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(BACKFILL_TIME)
    stored = await bot.database_text()

    await alice.send("/leave")
    await alice.press("Delete my data")
    after_leaving = await bot.database_text()

    assert {"member_gameweeks", "member_picks"} <= tables_with_rows(stored)
    # Kept: reference data (not about anyone), the current season and the used invite.
    assert tables_with_rows(after_leaving) == {
        "alembic_version",
        "seasons",
        "invites",
        "clubs",
        "footballers",
        "gameweeks",
        "fixtures",
    }


async def test_raw_fpl_responses_are_not_stored(bot: BotHarness) -> None:
    await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(BACKFILL_TIME)

    stored = await bot.database_text()

    # Fields the bot has no use for: the manager's surname, past seasons, percentile ranks.
    for raw in ["Kestrel", "2025/26", "percentile", "automatic_subs", "Nowhereland"]:
        assert raw not in stored


async def test_squad_works_from_stored_data_after_a_restart_while_fpl_is_down(
    bot: BotHarness,
) -> None:
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(BACKFILL_TIME)
    await alice.send("/squad")
    before = alice.last_reply

    await bot.restart()
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    await alice.send("/squad")

    assert alice.last_reply == before


async def test_with_fpl_down_and_nothing_stored_squad_says_fpl_is_unreachable(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(BACKFILL_TIME)

    await alice.send("/squad")

    assert alice.last_reply == "I can't reach FPL right now. Try again in a few minutes."


async def test_fpl_failing_during_the_backfill_gets_the_clear_message(bot: BotHarness) -> None:
    bot.fpl.respond("entry/1001/history/", canned_fpl_response("502-bad-gateway"))
    alice = await bot.active_member(user_id=2001, team_id=1001)
    await bot.advance(BACKFILL_TIME)

    await alice.send("/squad")

    assert alice.last_reply.startswith(
        "I don't have your Squad from the GW10 deadline: FPL isn't showing those picks."
    )


async def test_missing_picks_for_the_last_deadline_get_a_clear_message(bot: BotHarness) -> None:
    # Team 1002 played GW10, but FPL answers 404 for its GW10 picks.
    bob = await bot.active_member(user_id=2002, team_id=1002)
    await bot.advance(BACKFILL_TIME)

    await bob.send("/squad")

    assert bob.last_reply == (
        "I don't have your Squad from the GW10 deadline: FPL isn't showing those picks. "
        "Try /squad again later.\n"
        "\n"
        "FPL hides GW11 picks until the deadline (Sat 21 Nov 11:00 your time), so changes "
        "you've made since GW10 don't show yet."
    )
