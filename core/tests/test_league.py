"""Ticket 32: Followed leagues, the Gameweek-final job and ``/league``.

The default clock is Thursday 19 Nov 2026 18:00 UTC: GW10 is finished and checked, GW11's
deadline is Sat 21 Nov 11:00 UTC. Team 1001 (Alex's Aces) is in the Office League (501, 8
managers), Sunday Pub XI (502) and the head-to-head Cup Rivals H2H (601); team 1002 (Bojan United)
is in the Office League only. Standings are synthetic fixtures under ``leagues-classic/``.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from fplbot.sources.fpl import FplResponse
from tests.harness import FPL_FIXTURES, BotHarness, Chat

# Long enough for the Followed-league refresh and join backfill (rate-limited requests).
SETTLE = timedelta(minutes=1)

# (rank, last rank, points, team ID, team name)
type Row = tuple[int, int, int, int, str]


def standings(
    name: str, rows: list[Row], *, page: int = 1, has_next: bool = False, first: int = 1
) -> FplResponse:
    """A synthetic ``leagues-classic/{id}/standings/`` page; ``first`` is its first row's
    place in FPL's order."""
    data: dict[str, Any] = {
        "league": {"id": 1, "name": name, "league_type": "x", "scoring": "c"},
        "new_entries": {"has_next": False, "page": 1, "results": []},
        "standings": {
            "has_next": has_next,
            "page": page,
            "results": [
                {
                    "id": 80000 + first + i,
                    "event_total": 50,
                    "player_name": "Somebody Synthetic",
                    "rank": rank,
                    "last_rank": last_rank,
                    "rank_sort": first + i,
                    "total": points,
                    "entry": entry,
                    "entry_name": team,
                }
                for i, (rank, last_rank, points, entry, team) in enumerate(rows)
            ],
        },
    }
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


async def member_with_goal(
    bot: BotHarness, user_id: int, team_id: int, league: str | None = None
) -> Chat:
    """A Member who finished setup with Goal ``league`` (a Mini-league name) or Overall rank."""
    member = await bot.invited_friend(user_id)
    await member.send(str(team_id))
    await member.press("Yes, that's me")
    if league is None:
        await member.press("Overall rank")
    else:
        await member.press("Mini-league")
        await member.press(league)
    await member.press("Europe/London")
    assert member.last_reply.startswith("You're all set"), member.last_reply
    await bot.advance(SETTLE)
    return member


async def test_league_shows_the_goal_league_table_with_movement_and_gaps(bot: BotHarness) -> None:
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")

    await alice.send("/league")

    assert alice.last_reply == (
        "Office League · after GW10\n"
        " 1 –  Dave's Dynamos       540\n"
        " 2 ▲1 Priya's Picks        531\n"
        " 3 ▲2 Alex's Aces          512  ← you\n"
        " 4 ▼2 Tomo Town            505\n"
        " 5 ▼1 Bojan United         478\n"
        " 6 –  Marko's Men          466\n"
        " 7 ▲1 Sam's Side           450\n"
        " 8 ▼1 Rui Rovers           431\n"
        "\n"
        "19 pts behind Priya's Picks\n"
        "7 pts ahead of Tomo Town\n"
        "Leader 28 pts clear of you"
    )


async def test_a_member_on_top_gets_only_the_lines_that_apply(bot: BotHarness) -> None:
    bot.fpl.respond(
        "leagues-classic/501/standings/",
        standings(
            "Office League",
            [
                (1, 2, 560, 1001, "Alex's Aces"),
                (2, 1, 548, 3001, "Dave's Dynamos"),
                (3, 3, 530, 3002, "Priya's Picks"),
            ],
        ),
    )
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")

    await alice.send("/league")

    assert alice.last_reply == (
        "Office League · after GW10\n"
        " 1 ▲1 Alex's Aces          560  ← you\n"
        " 2 ▼1 Dave's Dynamos       548\n"
        " 3 –  Priya's Picks        530\n"
        "\n"
        "12 pts ahead of Dave's Dynamos\n"
        "Leader is you"
    )


async def test_a_member_at_the_bottom_gets_only_the_lines_that_apply(bot: BotHarness) -> None:
    bot.fpl.respond(
        "leagues-classic/501/standings/",
        standings(
            "Office League",
            [
                (1, 1, 560, 3001, "Dave's Dynamos"),
                (2, 2, 548, 3002, "Priya's Picks"),
                (3, 3, 530, 1001, "Alex's Aces"),
            ],
        ),
    )
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")

    await alice.send("/league")

    assert alice.last_reply == (
        "Office League · after GW10\n"
        " 1 –  Dave's Dynamos       560\n"
        " 2 –  Priya's Picks        548\n"
        " 3 –  Alex's Aces          530  ← you\n"
        "\n"
        "18 pts behind Priya's Picks\n"
        "Leader 30 pts clear of you"
    )


def big_league_page(page: int, size: int, you_at: int) -> FplResponse:
    """Page ``page`` of a ``size``-manager Office League: "Team 001", "Team 002"... in order,
    2 points apart, with team 1001 (Alex's Aces) at place ``you_at``."""
    first = (page - 1) * 50 + 1
    rows: list[Row] = [
        (p, p, 2000 - 2 * p, 1001, "Alex's Aces")
        if p == you_at
        else (p, p, 2000 - 2 * p, 5000 + p, f"Team {p:03}")
        for p in range(first, min(first + 50, size + 1))
    ]
    return standings("Office League", rows, page=page, has_next=first + 49 < size, first=first)


def entry_1001_ranked(league_id: int, rank: int) -> FplResponse:
    data = json.loads((FPL_FIXTURES / "entry/1001.json").read_text())
    for league in data["leagues"]["classic"]:
        if league["id"] == league_id:
            league["entry_rank"] = rank
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


async def test_a_goal_league_above_50_shows_only_the_followed_subset_and_says_so(
    bot: BotHarness,
) -> None:
    for page in (1, 2, 3, 4):
        path = "leagues-classic/501/standings/" + (f"?page_standings={page}" if page > 1 else "")
        bot.fpl.respond(path, big_league_page(page, size=180, you_at=60))
    alice = await bot.invited_friend(2001)
    await alice.send("1001")
    await alice.press("Yes, that's me")
    bot.fpl.respond("entry/1001/", entry_1001_ranked(501, rank=60))
    await alice.press("Mini-league")
    await alice.press("Office League")
    await alice.press("Europe/London")
    await bot.advance(SETTLE)

    await alice.send("/league")

    lines = alice.last_reply.split("\n")
    table = lines[1 : lines.index("")]
    shown = [int(line[:2]) for line in table if line.strip() != "…"]
    assert lines[0] == "Office League · after GW10"
    assert shown == [*range(1, 11), *range(40, 81)]
    assert table[10] == "   …"
    assert table[11 + 20] == "60 –  Alex's Aces          1880  ← you"
    assert lines[lines.index("") + 1 :] == [
        "Big league: showing the top 10 and the 20 managers directly above and below you.",
        "2 pts behind Team 059",
        "2 pts ahead of Team 061",
        "Leader 118 pts clear of you",
    ]
    standings_pages = {p for p in bot.fpl.requested_paths if p.startswith("leagues-classic/501")}
    assert standings_pages == {
        "leagues-classic/501/standings",
        "leagues-classic/501/standings/?page_standings=2",
    }


def bootstrap_with_gw11_final() -> FplResponse:
    data = json.loads((FPL_FIXTURES / "bootstrap-static.json").read_text())
    for event in data["events"]:
        if event["id"] == 11:
            event["finished"] = event["data_checked"] = True
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


OFFICE_LEAGUE_AFTER_GW11: list[Row] = [
    (1, 1, 601, 3001, "Dave's Dynamos"),
    (2, 3, 588, 1001, "Alex's Aces"),
    (3, 2, 580, 3002, "Priya's Picks"),
    (4, 4, 560, 3004, "Tomo Town"),
    (5, 5, 530, 1002, "Bojan United"),
    (6, 6, 512, 3006, "Marko's Men"),
    (7, 8, 470, 3008, "Rui Rovers"),
    (8, 7, 468, 3007, "Sam's Side"),
]


async def advance_to(bot: BotHarness, moment: datetime) -> None:
    await bot.advance(moment - bot.clock.now())


async def test_after_the_gameweek_final_tick_league_shows_the_new_table_and_a_rerun_is_a_no_op(
    bot: BotHarness,
) -> None:
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    await bot.start_scheduling()
    # GW11 is played on Saturday; FPL has not finished checking it by Saturday evening.
    await advance_to(bot, datetime.fromisoformat("2026-11-21T20:00:00Z"))
    await alice.send("/league")
    before = alice.last_reply
    bot.fpl.respond("bootstrap-static/", bootstrap_with_gw11_final())
    bot.fpl.respond(
        "leagues-classic/501/standings/", standings("Office League", OFFICE_LEAGUE_AFTER_GW11)
    )

    await advance_to(bot, datetime.fromisoformat("2026-11-22T12:00:00Z"))
    await alice.send("/league")

    assert before.startswith("Office League · after GW10\n 1 –  Dave's Dynamos       540\n")
    assert alice.last_reply == (
        "Office League · after GW11\n"
        " 1 –  Dave's Dynamos       601\n"
        " 2 ▲1 Alex's Aces          588  ← you\n"
        " 3 ▼1 Priya's Picks        580\n"
        " 4 –  Tomo Town            560\n"
        " 5 –  Bojan United         530\n"
        " 6 –  Marko's Men          512\n"
        " 7 ▲1 Rui Rovers           470\n"
        " 8 ▼1 Sam's Side           468\n"
        "\n"
        "13 pts behind Dave's Dynamos\n"
        "8 pts ahead of Priya's Picks\n"
        "Leader 13 pts clear of you"
    )

    stored = await bot.database_text()
    sent, requested = len(bot.telegram.calls), len(bot.fpl.requests)
    succeeded = await bot.run_job("gw-final", bot.app.gameweek_final.job(refresh=True))

    assert succeeded
    assert await bot.database_text() == stored
    assert len(bot.fpl.requests) == requested
    assert len(bot.telegram.calls) == sent


async def test_a_league_no_member_follows_any_more_stops_being_refreshed(bot: BotHarness) -> None:
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Office League")
    bob = await member_with_goal(bot, user_id=2002, team_id=1002)
    await bot.start_scheduling()
    await bot.advance(SETTLE)
    followed_before = await bot.database_text()

    await alice.send("/leave")
    await alice.press("Delete my data")
    after_leaving = await bot.database_text()
    left_at = len(bot.fpl.requests)
    await advance_to(bot, datetime.fromisoformat("2026-11-21T20:00:00Z"))
    bot.fpl.respond("bootstrap-static/", bootstrap_with_gw11_final())
    await advance_to(bot, datetime.fromisoformat("2026-11-22T12:00:00Z"))
    await bob.send("/league")

    refreshed = {r.path for r in bot.fpl.requests[left_at:] if "standings" in r.path}
    assert "Sunday Pub XI" in followed_before
    assert "Cup Rivals H2H" in followed_before
    assert "Sunday Pub XI" not in after_leaving
    assert "Cup Rivals H2H" not in after_leaving
    assert "Alex's Aces" in after_leaving  # still a row of the Office League Bob follows
    assert refreshed == {"leagues-classic/501/standings"}
    assert bob.last_reply.startswith("Office League · after GW11\n")


def h2h_match(home: tuple[int, str], away: tuple[int | None, str]) -> FplResponse:
    data: dict[str, Any] = {
        "has_next": False,
        "page": 1,
        "results": [
            {
                "id": 77001,
                "entry_1_entry": home[0],
                "entry_1_name": home[1],
                "entry_1_player_name": "Somebody Synthetic",
                "entry_1_points": 0,
                "entry_2_entry": away[0],
                "entry_2_name": away[1],
                "entry_2_player_name": "Somebody Else",
                "entry_2_points": 0,
                "event": 11,
                "is_knockout": False,
            }
        ],
    }
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


async def test_a_head_to_head_goal_league_also_names_the_next_opponent(bot: BotHarness) -> None:
    bot.fpl.respond(
        "leagues-h2h-matches/league/601/?event=11&entry=1001&page=1",
        h2h_match((3203, "Rival Rovers"), (1001, "Alex's Aces")),
    )
    alice = await member_with_goal(bot, user_id=2001, team_id=1001, league="Cup Rivals H2H")

    await alice.send("/league")

    assert alice.last_reply == (
        "Cup Rivals H2H · after GW10\n"
        " 1 –  Knockout Kings       24\n"
        " 2 ▲1 Alex's Aces          21  ← you\n"
        " 3 ▼1 Rival Rovers         18\n"
        " 4 –  Draw Specialists     13\n"
        " 5 –  Cup Upsetters        9\n"
        " 6 –  Wooden Spooners      4\n"
        "\n"
        "3 pts behind Knockout Kings\n"
        "3 pts ahead of Rival Rovers\n"
        "Leader 3 pts clear of you\n"
        "GW11 opponent: Rival Rovers"
    )


async def test_league_explains_when_there_is_no_table_to_show(bot: BotHarness) -> None:
    clara = await member_with_goal(bot, user_id=2003, team_id=1003)

    await clara.send("/league")

    assert clara.last_reply == (
        "No league table to show yet. I follow your Mini-leagues of up to 50 managers, and your "
        "Goal league whatever its size. If you've just joined or changed /goal, try again in a "
        "few minutes."
    )
