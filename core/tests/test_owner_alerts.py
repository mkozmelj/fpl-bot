"""Ticket 27: the owner hears about trouble once per incident, and once when it clears."""

from datetime import timedelta

from fplbot.sources.fpl import FplSource
from tests.harness import BotHarness, canned_fpl_response, fpl_fixture

BLOCKED = (
    "FPL-403: the picks job failed. FPL refused access (403). Not retried; the job waits for "
    "its next run."
)
DOWN = "FPL-DOWN: the prices job failed. FPL kept failing (429/5xx) after 5 tries."


async def read_bootstrap(fpl: FplSource) -> None:
    await fpl.bootstrap_static(max_age=timedelta(0))


async def read_team(fpl: FplSource) -> None:
    await fpl.get_json("entry/1001/")


async def test_a_403_tells_the_owner_at_once_and_a_later_success_says_recovered(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("entry/1001/", canned_fpl_response("403-forbidden"))
    await bot.run_job("picks", read_team)
    told_at_once = list(bot.owner.replies)

    await bot.advance(timedelta(hours=1))
    bot.fpl.respond("entry/1001/", fpl_fixture("bootstrap-static/"))
    await bot.run_job("picks", read_team)
    await bot.run_job("picks", read_team)

    assert told_at_once == [BLOCKED]
    assert bot.owner.replies == [BLOCKED, "FPL-403: the picks job has recovered."]


async def test_failures_with_a_success_between_them_are_not_reported(bot: BotHarness) -> None:
    failing = canned_fpl_response("502-bad-gateway")
    bot.fpl.respond("bootstrap-static/", *[failing] * 5, fpl_fixture("bootstrap-static/"), failing)

    outcomes = [await bot.run_job("prices", read_bootstrap) for _ in range(3)]

    assert outcomes == [False, True, False]
    assert bot.owner.replies == []


async def test_a_second_failure_in_a_row_tells_the_owner_and_a_third_does_not(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))

    await bot.run_job("prices", read_bootstrap)
    await bot.run_job("prices", read_bootstrap)
    after_second = list(bot.owner.replies)
    await bot.advance(timedelta(hours=5, minutes=50))
    await bot.run_job("prices", read_bootstrap)

    assert after_second == [DOWN]
    assert bot.owner.replies == [DOWN]


async def test_a_persisting_incident_is_reminded_at_most_every_6_hours(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    await bot.run_job("prices", read_bootstrap)
    await bot.run_job("prices", read_bootstrap)  # told, 18:00 UTC plus the retries

    for _ in range(4):  # failing every 2 hours for 8 hours
        await bot.advance(timedelta(hours=2))
        await bot.run_job("prices", read_bootstrap)

    assert bot.owner.replies == [
        DOWN,
        "FPL-DOWN: the prices job is still failing (since 19 Nov 18:00 UTC).",
    ]


async def test_failures_of_different_jobs_are_not_in_a_row(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))

    await bot.run_job("prices", read_bootstrap)
    await bot.run_job("picks", read_bootstrap)

    assert bot.owner.replies == []


async def test_a_crashing_job_tells_the_owner_a_fixed_code_and_nothing_else(
    bot: BotHarness,
) -> None:
    async def crashes(fpl: FplSource) -> None:
        raise RuntimeError("member 7 team 1001 Pseudonymia")

    await bot.run_job("gw-final", crashes)
    await bot.run_job("gw-final", crashes)

    assert bot.owner.replies == [
        "JOB-ERROR: the gw-final job failed. Unexpected error; see the logs."
    ]
    assert not [line for line in bot.logs if "1001" in line or "Pseudonymia" in line]
