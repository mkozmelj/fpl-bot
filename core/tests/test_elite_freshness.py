"""Ticket 35: the top 100k cohort and honest Elite figures when the sampler doesn't finish.

Builds on ``test_elite_gap.py`` (same clock, Squads and weights). The test "top 100k" is the
first 400 managers of the overall league: the top-10k stratum (ranks 1-40, a tenth of the
cohort, sample 20 as in ticket 34) plus a second stratum of ranks 41-400 (nine tenths, sample
20, all fielding ``deeper_squad``). A share of the top 100k is 0.1 x top-10k share + 0.9 x
second-stratum share; its margin of error combines both strata: ±19.3%.

Top 100k XI shares: Testkeeper, Fakesson, Gatekeep, Benchwood, Backline, Blockley, Sparesby,
Strikewell 100%; Wallace 92.5%; Passmore and Dribbleton 90%; Lastpick 9.5%; Tackleton 8%;
Reservo and Placeholder 5%; Crossley 0%. Captain: Strikewell 96%, Fakesson 4%.
"""

from datetime import datetime, timedelta

from tests.harness import BotHarness, canned_fpl_response
from tests.test_elite_gap import SAMPLED, after_the_gw11_run, script_gw11
from tests.test_league import advance_to, member_with_goal
from tests.test_rivals import your_gw10_squad

GW11_DEADLINE = datetime.fromisoformat("2026-11-21T11:00:00Z")
GW12_DEADLINE = datetime.fromisoformat("2026-11-28T11:00:00Z")
SETTLE = timedelta(minutes=2)

EXPLAINED_100K = (
    "Edge = points per GW you gain (+) or give up (−) against the average top 100k manager, "
    "weighted by average points over the last 4 Gameweeks."
)


async def test_gap_100k_compares_against_the_top_100k_with_its_own_sample_and_margin(
    elite_bot: BotHarness,
) -> None:
    alice = await after_the_gw11_run(elite_bot)

    await alice.send("/gap 100k")

    # Passmore, Dribbleton and Wallace no longer show: the top 100k mostly starts them too.
    # Benchwood (−0.25) and Lastpick (−0.2) are worth too little.
    assert alice.last_reply == (
        "Elite gap · top 100k · starting XI\n"
        "GW11 · sample 40 · ±19.3%\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "\n"
        f"{EXPLAINED_100K}\n"
        "\n"
        "You back, they mostly don't\n"
        "  Tackleton: you start · they 8% · +1.8\n"
        "  Crossley: you start · they 0% · +1.8\n"
        "  Placeholder: you start · they 5% · +0.5\n"
        "\n"
        "They back, you don't\n"
        "  Sparesby: you don't · they 100% · −4.0\n"
        "  Testkeeper: you don't · they 100% · −3.5"
    )


async def test_gap_100k_captain_shows_the_top_100k_captains(elite_bot: BotHarness) -> None:
    alice = await after_the_gw11_run(elite_bot)

    await alice.send("/gap 100k captain")

    assert alice.last_reply == (
        "Elite gap · top 100k · captain\n"
        "GW11 · sample 40 · ±19.3%\n"
        "Squad as of the GW11 deadline. GW12 picks are hidden until its deadline.\n"
        "\n"
        f"{EXPLAINED_100K}\n"
        "\n"
        "You back, they mostly don't\n"
        "  Fakesson: you captain him · they 4% · +5.8\n"
        "\n"
        "They back, you don't\n"
        "  Strikewell: you don't · they 96% · −4.8"
    )


def fpl_down_from(bot: BotHarness, entry: int, gameweek: int = 11) -> None:
    """FPL fails for good (502 on every try) from this sampled manager's Squad on."""
    bot.fpl.respond(f"entry/{entry}/event/{gameweek}/picks/", canned_fpl_response("502-bad-gateway"))


async def test_a_sample_that_stops_past_half_its_target_is_published_as_partial(
    elite_bot: BotHarness,
) -> None:
    script_gw11(elite_bot)
    fpl_down_from(elite_bot, SAMPLED[12])  # 12 of the 20 top-10k Squads are read
    alice = await member_with_goal(elite_bot, user_id=2001, team_id=1001)
    await elite_bot.start_scheduling(price_history=False)
    await advance_to(elite_bot, GW11_DEADLINE + timedelta(minutes=30))

    await alice.send("/gap")
    top_10k = alice.last_reply
    await alice.send("/gap 100k")

    # 12 of 40 managers: ±24.0% instead of ±15.7%.
    assert top_10k.startswith(
        "Elite gap · top 10k · starting XI\nGW11 · sample 12 · ±24.0% (partial sample)\n"
    )
    # The top 100k's second stratum was never reached: no figures, rather than mixed ones.
    assert alice.last_reply == (
        "Elite gap · top 100k\nNo Elite figures yet for GW11.\nTry /rivals meanwhile."
    )


async def test_a_sample_below_half_its_target_keeps_last_gameweeks_figures_with_a_warning(
    elite_bot: BotHarness,
) -> None:
    alice = await after_the_gw11_run(elite_bot)
    await alice.send("/gap")
    gw11 = alice.last_reply.split("\n")
    # GW12: only 5 of the 20 top-10k Squads are read before FPL goes down. They field Alice's
    # own Squad, so any of them leaking into the figures would change the Gap.
    for entry in (*SAMPLED[:5], 1001):
        elite_bot.fpl.respond(f"entry/{entry}/event/12/picks/", your_gw10_squad(gameweek=12))
    fpl_down_from(elite_bot, SAMPLED[5], gameweek=12)
    await elite_bot.app.scheduler.stop()  # skip a week of hourly jobs: run GW12's by hand
    await advance_to(elite_bot, GW12_DEADLINE + timedelta(minutes=5))
    await elite_bot.run_job("picks", elite_bot.app.post_deadline.picks_job(12))

    await alice.send("/gap")
    top_10k = alice.last_reply.split("\n")
    await alice.send("/gap 100k captain")

    assert top_10k[:3] == [
        "Elite gap · top 10k · starting XI",
        "⚠ Using GW11 figures (GW12 sample not finished).",
        "GW12 deadline has passed: Squads are locked.",
    ]
    assert top_10k[3:] == gw11[3:]  # GW11's figures, whole and alone
    assert alice.last_reply.startswith(
        "Elite gap · top 100k · captain\n⚠ Using GW11 figures (GW12 sample not finished).\n"
    )
