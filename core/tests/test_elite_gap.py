"""Ticket 34: the Elite gap (``/gap``) against the top 10k, from our own sample.

The default clock is Thursday 19 Nov 2026 18:00 UTC: GW10 is the last deadline, GW11's deadline
is Sat 21 Nov 11:00 UTC. No Elite figures exist before the first post-deadline run (GW11).

The ``elite_bot`` runs the sampler at test scale (``TEST_ELITE_DESIGN``): the cohort is the first
40 managers of the overall league (entries 7700001-7700040 here) and the sample is the 20
ranked highest. That gives a margin of error of ±15.7%, so an XI-share difference must beat
31.4% to show. Team 1001's Squad and the weights (average points over GW7-10) are as described
in ``test_rivals.py``: Alice starts Gatekeep, Backline, Wallace, Blockley, Tackleton, Fakesson
(C), Passmore, Dribbleton, Crossley, Placeholder and Strikewell.

The 20 sampled Squads all start Testkeeper 101, Fakesson 102, Gatekeep 201, Benchwood 202,
Backline 203, Blockley 205, Sparesby 207 and Strikewell 212, plus Tackleton 206 (16 of 20, 80%),
Reservo 211 (10, 50%), Placeholder 103 (10, 50%), Wallace 204 (5, 25%) and Lastpick 213 (19).
Nobody starts Passmore, Dribbleton or Crossley. 12 captain Strikewell (the first with the Triple
Captain chip), 8 Fakesson.

The test "top 100k" (ticket 35) is the first 400 managers: the 40 above plus a second stratum,
ranks 41-400, read as 2 standings pages (pages 1 and 2) with 10 managers from each (places
41-60). Those 20 all field the same Squad (``deeper_squad``).
"""

import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from fplbot.sources.fpl import FplResponse, FplSource, Priority
from tests.harness import BotHarness, Chat
from tests.test_league import Row, advance_to, member_with_goal, standings
from tests.test_rivals import your_gw10_squad

GW11_DEADLINE = datetime.fromisoformat("2026-11-21T11:00:00Z")
AFTER_THE_RUN = GW11_DEADLINE + timedelta(minutes=30)
SETTLE = timedelta(minutes=2)

ELITE = [7_700_000 + place for place in range(1, 101)]  # the overall league's first 2 pages
SAMPLED = ELITE[:20]
DEEPER_SAMPLED = ELITE[40:60]  # the test top 100k's second stratum

ALL_START = [101, 102, 201, 202, 203, 205, 207, 212]
NOBODY_STARTS = [208, 209, 210]


def overall_league_page(page: int = 1) -> FplResponse:
    first = (page - 1) * 50 + 1
    rows: list[Row] = [
        (place, place, 900 - place, ELITE[place - 1], f"Elite {place:03}")
        for place in range(first, first + 50)
    ]
    return standings("Overall", rows, page=page, has_next=True, first=first)


def script_overall_league(bot: BotHarness) -> None:
    bot.fpl.respond("leagues-classic/314/standings/", overall_league_page(1))
    bot.fpl.respond("leagues-classic/314/standings/?page_standings=2", overall_league_page(2))


def elite_picks(
    xi: Sequence[int], bench: Sequence[int], captain: int, chip: str | None = None
) -> FplResponse:
    triple = chip == "3xc"
    data: dict[str, Any] = {
        "active_chip": chip,
        "automatic_subs": [],
        "entry_history": {"event": 11},
        "picks": [
            {
                "element": footballer,
                "position": slot,
                "multiplier": ((3 if triple else 2) if footballer == captain else 1)
                if slot <= 11
                else 0,
                "is_captain": footballer == captain,
                "is_vice_captain": False,
                "element_type": 1,
            }
            for slot, footballer in enumerate([*xi, *bench], start=1)
        ],
    }
    return FplResponse(200, json.dumps(data).encode(), {"content-type": "application/json"})


def sampled_squad(i: int) -> FplResponse:
    """The ``i``-th (0-19) sampled manager's GW11 Squad (see the module docstring)."""
    extra = [206] if i < 16 else []
    extra += [211] if i < 10 else [103]
    extra += [204] if i >= 15 else []
    extra += [213] if len(extra) < 3 else []
    xi = [*ALL_START, *extra]
    bench = [f for f in (*NOBODY_STARTS, 211, 204, 206, 103, 213) if f not in xi][:4]
    captain = 212 if i < 12 else 102
    return elite_picks(xi, bench, captain, chip="3xc" if i == 0 else None)


def deeper_squad() -> FplResponse:
    """Every sampled manager of the test top 100k's second stratum: Passmore, Dribbleton and
    Wallace start, Strikewell is captain."""
    return elite_picks([*ALL_START, 208, 209, 204], [103, 206, 211, 213], captain=212)


def script_gw11(bot: BotHarness, yours: FplResponse | None = None) -> None:
    """The overall league, the sampled Squads and team 1001's GW11 Squad (default: its GW10
    one again)."""
    script_overall_league(bot)
    for i, entry in enumerate(SAMPLED):
        bot.fpl.respond(f"entry/{entry}/event/11/picks/", sampled_squad(i))
    for entry in DEEPER_SAMPLED:
        bot.fpl.respond(f"entry/{entry}/event/11/picks/", deeper_squad())
    bot.fpl.respond("entry/1001/event/11/picks/", yours or your_gw10_squad(gameweek=11))


async def after_the_gw11_run(bot: BotHarness, yours: FplResponse | None = None) -> Chat:
    script_gw11(bot, yours)
    alice = await member_with_goal(bot, user_id=2001, team_id=1001)
    await bot.start_scheduling(price_history=False)
    await bot.advance(SETTLE)
    await advance_to(bot, AFTER_THE_RUN)
    return alice


EXPLAINED = (
    "Edge = points per GW you gain (+) or give up (−) against the average top 10k manager, "
    "weighted by average points over the last 4 Gameweeks."
)


async def test_before_the_first_sample_gap_says_so_and_points_to_rivals(bot: BotHarness) -> None:
    alice = await member_with_goal(bot, user_id=2001, team_id=1001)

    await alice.send("/gap")

    assert alice.last_reply == (
        "Elite gap · top 10k\nNo Elite figures yet for GW10.\nTry /rivals meanwhile."
    )


async def test_after_the_post_deadline_run_gap_shows_at_most_3_a_side_beyond_the_noise(
    elite_bot: BotHarness,
) -> None:
    alice = await after_the_gw11_run(elite_bot)

    await alice.send("/gap")

    # Hidden: Dribbleton (4th on its side), Tackleton (80% vs you: inside 2x the margin of
    # error), Placeholder (50%, but only 0.25 pts a GW), Strikewell and Fakesson (both start
    # him: a captain difference is not an XI difference).
    assert alice.last_reply == (
        "Elite gap · top 10k · starting XI\n"
        "GW11 · sample 20 · ±15.7%\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "\n"
        f"{EXPLAINED}\n"
        "\n"
        "You back, they mostly don't\n"
        "  Passmore: you start · they 0% · +4.0\n"
        "  Wallace: you start · they 25% · +2.3\n"
        "  Crossley: you start · they 0% · +1.8\n"
        "\n"
        "They back, you don't\n"
        "  Sparesby: you don't · they 100% · −4.0\n"
        "  Testkeeper: you don't · they 100% · −3.5\n"
        "  Reservo: you don't · they 50% · −1.0"
    )


async def test_gap_captain_shows_the_captain_part_alone(elite_bot: BotHarness) -> None:
    alice = await after_the_gw11_run(elite_bot)

    await alice.send("/gap captain")

    assert alice.last_reply == (
        "Elite gap · top 10k · captain\n"
        "GW11 · sample 20 · ±15.7%\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "\n"
        f"{EXPLAINED}\n"
        "\n"
        "You back, they mostly don't\n"
        "  Fakesson: you captain him · they 40% · +3.6\n"
        "\n"
        "They back, you don't\n"
        "  Strikewell: you don't · they 60% · −3.0"
    )


async def test_differences_inside_twice_the_margin_of_error_or_under_035_pts_are_hidden(
    elite_bot: BotHarness,
) -> None:
    # Alice starts what the Elite mostly starts, plus Tackleton (they 80%), Placeholder (50%)
    # and Lastpick (95%), and captains Strikewell. Wallace (they 25%, you don't) would be
    # -0.8 and Tackleton +0.4, but each differs by less than 2x ±15.7%; Placeholder differs
    # by 50% but is worth only 0.25 pts a GW. Only Reservo (50%, -1.0) beats both.
    yours = elite_picks([*ALL_START, 206, 103, 213], [*NOBODY_STARTS, 204], captain=212)
    alice = await after_the_gw11_run(elite_bot, yours)

    await alice.send("/gap")

    assert alice.last_reply.split("\n\n", 2)[2] == (
        "They back, you don't\n  Reservo: you don't · they 50% · −1.0"
    )


async def test_with_nothing_beyond_the_noise_you_look_like_the_template(
    elite_bot: BotHarness,
) -> None:
    for entry in (*SAMPLED, *DEEPER_SAMPLED, 1001):  # the whole sample fields Alice's Squad
        elite_bot.fpl.respond(f"entry/{entry}/event/11/picks/", your_gw10_squad(gameweek=11))
    script_overall_league(elite_bot)
    alice = await member_with_goal(elite_bot, user_id=2001, team_id=1001)
    await elite_bot.start_scheduling(price_history=False)
    await advance_to(elite_bot, AFTER_THE_RUN)

    await alice.send("/gap")

    assert alice.last_reply == (
        "Elite gap · top 10k · starting XI\n"
        "GW11 · sample 20 · ±15.7%\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "\n"
        f"{EXPLAINED}\n"
        "\n"
        "No difference larger than the margin of error: you look like the template."
    )


async def test_only_aggregates_survive_the_run_never_a_sampled_manager_or_pick(
    elite_bot: BotHarness,
) -> None:
    await after_the_gw11_run(elite_bot)

    stored = await elite_bot.database_text()

    # Per Footballer: ownership, XI share, captain share, EO. Strikewell: everyone starts him,
    # 12 of 20 captain him, one with the Triple Captain: EO (11*2 + 3 + 8) / 20.
    assert "elite_ownership: ('2026-27', 11, '10k', 212, 1.0, 1.0, 0.6, 1.65)" in stored
    # Wallace: 5 start him, 10 more have him on the bench.
    assert "elite_ownership: ('2026-27', 11, '10k', 204, 0.75, 0.25, 0.0, 0.25)" in stored
    assert "elite_chips: ('2026-27', 11, '10k', '3xc', 0.05)" in stored
    assert "elite_samples: ('2026-27', 11, '10k', 40, 20, 20, 0.1569" in stored
    assert "job_completions: ('2026-27', 'elite', 'gw11'," in stored
    assert "77000" not in stored  # no cohort or sampled entry ID, no Elite Squad
    assert not [line for line in elite_bot.logs if "77000" in line]


async def test_the_sampler_lets_every_other_fpl_request_go_first(elite_bot: BotHarness) -> None:
    script_gw11(elite_bot)
    await advance_to(elite_bot, GW11_DEADLINE + timedelta(minutes=5))
    elite_bot.start_job("picks", elite_bot.app.post_deadline.picks_job(11))
    while not any(r.path.startswith("entry/77000") for r in elite_bot.fpl.requests):
        await elite_bot.advance(timedelta(seconds=1))
    others = ["entry/1001/history", "entry/1002/history", "entry/1003/history"]

    async def routine_job(fpl: FplSource) -> None:  # e.g. a Member's join backfill
        for path in others:
            await fpl.get_json(path)

    elite_bot.start_job("backfill", routine_job, Priority.ROUTINE)
    await elite_bot.advance(timedelta(minutes=1))

    paths = elite_bot.fpl.requested_paths
    first = paths.index(others[0])
    assert paths[first : first + 3] == others  # not one sampler request in between
    assert paths[first + 3].startswith("entry/77000")  # the sampler carries on after them
    assert "job_completions: ('2026-27', 'elite', 'gw11'," in await elite_bot.database_text()


async def test_a_failed_cohort_read_keeps_the_members_picks_and_a_restart_samples_only(
    elite_bot: BotHarness,
) -> None:
    script_gw11(elite_bot)
    elite_bot.fpl.respond("leagues-classic/314/standings/", FplResponse(404, b"{}"))
    alice = await member_with_goal(elite_bot, user_id=2001, team_id=1001)
    await elite_bot.start_scheduling(price_history=False)
    await advance_to(elite_bot, AFTER_THE_RUN)
    await alice.send("/squad")
    squad = alice.last_reply
    await alice.send("/gap")
    not_ready = alice.last_reply

    script_overall_league(elite_bot)
    requested = len(elite_bot.fpl.requests)
    await elite_bot.restart()  # startup catch-up: GW11 has picks but no Elite sample
    await elite_bot.advance(SETTLE)
    await alice.send("/gap")

    assert "your Squad at the GW11 deadline" in squad
    assert not_ready == (
        "Elite gap · top 10k\nNo Elite figures yet for GW11.\nTry /rivals meanwhile."
    )
    assert alice.last_reply.startswith("Elite gap · top 10k · starting XI\nGW11 · sample 20")
    later = elite_bot.fpl.requested_paths[requested:]
    assert "entry/1001/event/11/picks" not in later
    assert len([p for p in later if p.startswith("entry/77000")]) == 40  # both strata


async def test_re_running_a_sampled_gameweek_makes_no_request(elite_bot: BotHarness) -> None:
    await after_the_gw11_run(elite_bot)
    stored = await elite_bot.database_text()
    requested = len(elite_bot.fpl.requests)

    await elite_bot.restart()
    await elite_bot.advance(SETTLE)
    succeeded = await elite_bot.run_job("picks", elite_bot.app.post_deadline.picks_job(11))

    later = elite_bot.fpl.requested_paths[requested:]
    assert succeeded
    assert not [p for p in later if "standings" in p or "picks" in p or p == "event-status"]
    assert await elite_bot.database_text() == stored


async def test_gap_with_an_unknown_view_says_how_to_use_it(elite_bot: BotHarness) -> None:
    alice = await member_with_goal(elite_bot, user_id=2001, team_id=1001)

    await alice.send("/gap everything")

    assert alice.last_reply == (
        "Use /gap for your starting XI against the top 10k, or /gap captain for captains alone."
    )
