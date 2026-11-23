"""Ticket 30: ``/squad`` and the join backfill.

Linking a team starts a background backfill of the Member's season history and past picks
(it runs at routine priority, so tests let simulated time pass for it). ``/squad`` shows the
Squad as of the last deadline. The default clock is Thursday 19 Nov 2026, after the GW10
deadline and before GW11's (Sat 21 Nov, 11:00 UTC).
"""

from datetime import timedelta

from tests.harness import BotHarness

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
