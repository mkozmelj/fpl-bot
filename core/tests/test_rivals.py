"""Ticket 33: the Rival gap (``/rivals``), Rival picks and per-Gameweek Footballer stats.

The default clock is Thursday 19 Nov 2026 18:00 UTC: GW10 is the last deadline (finished and
checked), GW11's deadline is Sat 21 Nov 11:00 UTC. Team 1001 (Alex's Aces) is 3rd in the Office
League (501); its nearest Rivals by rank are Dave's Dynamos (3001), Priya's Picks (3002), Tomo
Town (3004) and Bojan United (1002). Its Squad at the GW10 deadline:

    XI     Gatekeep 201, Backline 203, Wallace 204, Blockley 205, Tackleton 206, Fakesson 102 (C),
           Passmore 208, Dribbleton 209, Crossley 210, Placeholder 103, Strikewell 212
    bench  Benchwood 202, Sparesby 207, Reservo 211, Lastpick 213

Weights are average points over the last 4 finished Gameweeks (fixtures ``event/7-10/live``;
GW6 has much bigger numbers for Testkeeper and Passmore, which must not count):

    Testkeeper 101  3.5   Fakesson 102  6.0   Placeholder 103 0.5   Gatekeep 201   2.0
    Benchwood 202   0.25  Backline 203  1.0   Wallace 204     3.0   Blockley 205   0.75
    Tackleton 206   2.0   Sparesby 207  4.0   Passmore 208    4.0   Dribbleton 209 1.25
    Crossley 210    1.75  Reservo 211   2.0   Strikewell 212  5.0   Lastpick 213   0.25
"""

import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from fplbot.sources.fpl import FplResponse
from tests.harness import FPL_FIXTURES, BotHarness, fpl_fixture
from tests.test_league import advance_to, bootstrap_with_gw11_final, h2h_match, member_with_goal

SETTLE = timedelta(minutes=2)
GW11_DEADLINE = datetime.fromisoformat("2026-11-21T11:00:00Z")

ALL_STARTING = [101, 102, 201, 202, 206, 212, 213]


def picks(xi: Sequence[int], bench: Sequence[int], captain: int, gameweek: int = 10) -> FplResponse:
    """A synthetic ``entry/{id}/event/{gw}/picks/`` answer."""
    data: dict[str, Any] = {
        "active_chip": None,
        "automatic_subs": [],
        "entry_history": {"event": gameweek},
        "picks": [
            {
                "element": footballer,
                "position": slot,
                "multiplier": (2 if footballer == captain else 1) if slot <= 11 else 0,
                "is_captain": footballer == captain,
                "is_vice_captain": False,
                "element_type": 1,
            }
            for slot, footballer in enumerate([*xi, *bench], start=1)
        ],
    }
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


# Four Rival Squads. Across them, the starting shares are: Testkeeper, Fakesson, Gatekeep,
# Benchwood, Tackleton, Strikewell, Lastpick 4/4; Placeholder, Backline, Blockley 3/4; Wallace,
# Sparesby 2/4; Dribbleton, Crossley, Reservo 1/4; Passmore 0/4. A and B captain Fakesson,
# C and D Strikewell.
RIVAL_A = picks([*ALL_STARTING, 103, 203, 204, 205], [207, 208, 209, 210], captain=102)
RIVAL_B = RIVAL_A
RIVAL_C = picks([*ALL_STARTING, 103, 203, 205, 207], [204, 208, 209, 210], captain=212)
RIVAL_D = picks([*ALL_STARTING, 207, 209, 210, 211], [103, 203, 204, 208], captain=212)


def your_gw10_squad(gameweek: int = 10) -> FplResponse:
    data = json.loads((FPL_FIXTURES / "entry/1001/event/10/picks.json").read_text())
    data["entry_history"]["event"] = gameweek
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


def script_nearest_office_rivals(bot: BotHarness, gameweek: int = 10) -> None:
    for entry, answer in ((3001, RIVAL_A), (3002, RIVAL_B), (3004, RIVAL_C), (1002, RIVAL_D)):
        bot.fpl.respond(f"entry/{entry}/event/{gameweek}/picks/", answer)


async def scheduled(bot: BotHarness) -> None:
    """Production startup's scheduled work: catch-up and the Footballer-stats backfill."""
    await bot.start_scheduling(price_history=False)
    await bot.advance(SETTLE)


async def test_rivals_shows_at_most_3_footballers_a_side_against_the_nearest_4(
    bot: BotHarness,
) -> None:
    script_nearest_office_rivals(bot)
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    await scheduled(bot)

    await alice.send("/rivals")

    assert alice.last_reply == (
        "Rival gap · Office League · nearest 4 by rank\n"
        "Squad as of the GW10 deadline. GW11 picks are hidden until its deadline.\n"
        "Rival picks are also as of the last deadline.\n"
        "\n"
        "You back, they mostly don't\n"
        "  Passmore: you start · they 0% · +4.0\n"
        "  Wallace: you start · they 50% · +1.5\n"
        "  Crossley: you start · they 25% · +1.3\n"
        "\n"
        "They back, you don't\n"
        "  Testkeeper: you don't · they 100% · −3.5\n"
        "  Sparesby: you don't · they 50% · −2.0\n"
        "  Reservo: you don't · they 25% · −0.5\n"
        "\n"
        "Captain: Fakesson · 2 of 4 Rivals captain him too."
    )


async def test_rivals_all_uses_the_whole_goal_league_and_says_how_many(bot: BotHarness) -> None:
    script_nearest_office_rivals(bot)
    for entry in (3006, 3007, 3008):  # the rest of the Office League: like Rival A
        bot.fpl.respond(f"entry/{entry}/event/10/picks/", RIVAL_A)
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    await scheduled(bot)

    await alice.send("/rivals all")

    lines = alice.last_reply.split("\n")
    assert lines[0] == "Rival gap · Office League · all 7 Rivals"
    assert lines[-1] == "Captain: Fakesson · 5 of 7 Rivals captain him too."


async def test_with_overall_rank_as_goal_rivals_come_from_the_followed_league(
    bot: BotHarness,
) -> None:
    script_nearest_office_rivals(bot)
    alice = await member_with_goal(bot, user_id=2001, team_id=1001)
    await scheduled(bot)

    await alice.send("/rivals")

    assert alice.last_reply.startswith("Rival gap · Office League · nearest 4 by rank\n")
    assert alice.last_reply.endswith("Captain: Fakesson · 2 of 4 Rivals captain him too.")


async def test_a_head_to_head_opponent_is_a_single_rival(bot: BotHarness) -> None:
    bot.fpl.respond(
        "leagues-h2h-matches/league/601/?event=11&entry=1001&page=1",
        h2h_match((3203, "Rival Rovers"), (1001, "Alex's Aces")),
    )
    bot.fpl.respond("entry/3203/event/10/picks/", RIVAL_D)
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Cup Rivals H2H")
    await scheduled(bot)

    await alice.send("/rivals")

    assert alice.last_reply == (
        "Rival gap · Cup Rivals H2H · GW11 opponent Rival Rovers\n"
        "Squad as of the GW10 deadline. GW11 picks are hidden until its deadline.\n"
        "Rival picks are also as of the last deadline.\n"
        "\n"
        "You back, they don't\n"
        "  Passmore: you start · they 0% · +4.0\n"
        "  Wallace: you start · they 0% · +3.0\n"
        "  Backline: you start · they 0% · +1.0\n"
        "\n"
        "They back, you don't\n"
        "  Sparesby: you don't · they 100% · −4.0\n"
        "  Testkeeper: you don't · they 100% · −3.5\n"
        "  Reservo: you don't · they 100% · −2.0\n"
        "\n"
        "Captain: you Fakesson, they Strikewell."
    )


async def test_after_a_deadline_rivals_compares_the_new_squads_and_nothing_is_pushed(
    bot: BotHarness,
) -> None:
    script_nearest_office_rivals(bot)
    for entry in (1001, 3001, 3002, 3004, 1002):  # everyone fields Alice's Squad at GW11
        bot.fpl.respond(f"entry/{entry}/event/11/picks/", your_gw10_squad(gameweek=11))
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    await scheduled(bot)
    replies_before = len(alice.replies)

    await advance_to(bot, GW11_DEADLINE + timedelta(minutes=30))
    pushed = alice.replies[replies_before:]
    await alice.send("/rivals")

    assert pushed == []
    assert alice.last_reply == (
        "Rival gap · Office League · nearest 4 by rank\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "Rival picks are also as of the last deadline.\n"
        "\n"
        "Captain: Fakesson · 4 of 4 Rivals captain him too.\n"
        "No single Footballer stands out against these Rivals."
    )


async def test_rival_picks_go_once_no_member_follows_a_league_with_that_rival(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("entry/3001/event/10/picks/", RIVAL_A)  # Office League: Bob follows it too
    bot.fpl.respond("entry/3101/event/10/picks/", RIVAL_B)  # Sunday Pub XI: Alice's only
    bot.fpl.respond("entry/3203/event/10/picks/", RIVAL_C)  # Cup Rivals H2H: Alice's only
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    await member_with_goal(bot, user_id=2002, team_id=1002)
    stored = await bot.database_text()

    await alice.send("/leave")
    await alice.press("Delete my data")

    after = await bot.database_text()
    for team in (3001, 3101, 3203):
        assert f"rival_picks: ('2026-27', {team}, 10, 1," in stored
    assert "rival_picks: ('2026-27', 3001, 10, 1," in after
    assert "rival_picks: ('2026-27', 3101," not in after
    assert "rival_picks: ('2026-27', 3203," not in after


async def test_footballer_stats_are_read_once_per_finished_gameweek(bot: BotHarness) -> None:
    await scheduled(bot)  # launch backfill: GW1-10 are finished
    bot.fpl.respond("event/11/live/", fpl_fixture("event/10/live/"))
    bot.fpl.respond("bootstrap-static/", bootstrap_with_gw11_final())
    await advance_to(bot, datetime.fromisoformat("2026-11-22T12:00:00Z"))  # GW11 final
    await bot.restart()
    await bot.advance(SETTLE)

    live = sorted(r.path for r in bot.fpl.requests if r.path.endswith("/live"))
    assert live == sorted(f"event/{gw}/live" for gw in range(1, 12))
    assert "footballer_gameweek_stats: ('2026-27', 11, 101, 4," in await bot.database_text()
