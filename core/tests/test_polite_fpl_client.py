"""Ticket 27: every FPL request goes through one polite client.

No real job needs FPL yet, so these tests run small stand-in jobs through the bot's job runner
(``bot.start_job`` / ``bot.run_job``) and watch what reaches the fake FPL transport.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from itertools import pairwise

from fplbot.sources.fpl import FplResponse, FplSource, FplUpdating, Priority
from tests.harness import OWNER_ID, BotHarness, canned_fpl_response, fpl_fixture


def fetch_all(*paths: str) -> Callable[[FplSource], Awaitable[None]]:
    """A stand-in job that asks FPL for every path at once, like the Elite sampler's bursts."""

    async def job(fpl: FplSource) -> None:
        await asyncio.gather(*(fpl.get_json(path) for path in paths))

    return job


async def test_a_burst_from_two_jobs_never_exceeds_one_request_a_second(bot: BotHarness) -> None:
    bot.start_job("elite", fetch_all(*[f"entry/{i}/" for i in range(1, 7)]), Priority.ELITE)
    bot.start_job("picks", fetch_all(*[f"entry/{i}/" for i in range(11, 17)]), Priority.ROUTINE)

    await bot.advance(timedelta(seconds=30))

    started = [request.at for request in bot.fpl.requests]
    assert len(started) == 12
    assert min(later - earlier for earlier, later in pairwise(started)) >= timedelta(seconds=1)


async def test_interactive_work_overtakes_queued_elite_sampling(bot: BotHarness) -> None:
    bot.start_job("elite", fetch_all(*[f"entry/{i}/" for i in range(1, 11)]), Priority.ELITE)
    await bot.advance(timedelta(seconds=2.5))  # elite requests went out at 0, 1 and 2 s

    bot.start_job("lookup", fetch_all("entry/999/"), Priority.INTERACTIVE)
    await bot.advance(timedelta(seconds=30))

    assert bot.fpl.requested_paths.index("entry/999") == 3
    assert len(bot.fpl.requests) == 11


async def test_a_429_is_retried_after_its_retry_after_delay(bot: BotHarness) -> None:
    bot.fpl.respond(
        "bootstrap-static/",
        canned_fpl_response("429-retry-after"),  # Retry-After: 120
        fpl_fixture("bootstrap-static/"),
    )

    succeeded = await bot.run_job("prices", read_bootstrap)

    first, second = bot.fpl.requests
    assert succeeded
    assert timedelta(seconds=120) <= second.at - first.at < timedelta(seconds=121)
    assert bot.owner.replies == []


async def test_a_5xx_is_retried_with_growing_delays_and_given_up_after_5_tries(
    bot: BotHarness,
) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))

    succeeded = await bot.run_job("prices", read_bootstrap)

    tries = [request.at for request in bot.fpl.requests]
    waits = [later - earlier for earlier, later in pairwise(tries)]
    assert not succeeded
    assert len(tries) == 5
    assert waits == sorted(waits)
    assert waits[0] >= timedelta(seconds=1)
    assert waits[-1] > 4 * waits[0]


async def test_jittered_delays_differ_between_runs(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("502-bad-gateway"))
    for _ in range(3):
        await bot.run_job("prices", read_bootstrap)

    tries = [request.at for request in bot.fpl.requests]
    first_waits = {tries[run * 5 + 1] - tries[run * 5] for run in range(3)}
    assert len(first_waits) > 1


async def test_a_403_is_never_retried_and_the_job_stops_there(bot: BotHarness) -> None:
    bot.fpl.respond("entry/1001/", canned_fpl_response("403-forbidden"))

    async def picks(fpl: FplSource) -> None:
        await fpl.get_json("entry/1001/")
        await fpl.get_json("entry/1002/")

    succeeded = await bot.run_job("picks", picks)
    await bot.advance(timedelta(minutes=30))

    assert not succeeded
    assert bot.fpl.requested_paths == ["entry/1001"]


async def test_the_game_is_being_updated_is_not_retried_as_a_failure(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("503-updating"))
    told: list[bool] = []

    async def probe(fpl: FplSource) -> None:
        try:
            await fpl.bootstrap_static()
        except FplUpdating:
            told.append(True)

    await bot.run_job("post-deadline", probe)

    assert told == [True]
    assert bot.fpl.requested_paths == ["bootstrap-static"]


async def test_every_request_carries_only_the_generic_browser_headers(bot: BotHarness) -> None:
    bot.fpl.respond(
        "bootstrap-static/",
        canned_fpl_response("502-bad-gateway"),
        FplResponse(200, fpl_fixture("bootstrap-static/").body, {"etag": '"v1"'}),
        FplResponse(304, b"", {"etag": '"v1"'}),
    )

    async def mixed(fpl: FplSource) -> None:
        await fpl.bootstrap_static()
        await fpl.get_json("entry/1001/")
        await fpl.bootstrap_static(max_age=timedelta(0))

    await bot.run_job("mixed", mixed)

    assert len(bot.fpl.requests) == 4
    for request in bot.fpl.requests:
        headers = {name.lower(): value for name, value in request.headers.items()}
        assert headers["user-agent"].startswith("Mozilla/5.0 (")
        assert set(headers) <= {
            "user-agent",
            "accept",
            "accept-language",
            "if-none-match",
            "if-modified-since",
        }
        sent = " ".join(headers.values()).lower()
        for identifying in ["fplbot", "github", "telegram", "python", str(OWNER_ID), "test-token"]:
            assert identifying not in sent


async def test_a_resource_with_an_etag_is_fetched_conditionally(bot: BotHarness) -> None:
    fresh = fpl_fixture("bootstrap-static/")
    bot.fpl.respond(
        "bootstrap-static/",
        FplResponse(200, fresh.body, {"etag": '"v1"'}),
        FplResponse(304, b"", {"etag": '"v1"'}),
    )
    seen: list[int] = []

    async def count_footballers(fpl: FplSource) -> None:
        seen.append(len((await fpl.bootstrap_static(max_age=timedelta(0)))["elements"]))

    await bot.run_job("prices", count_footballers)
    await bot.run_job("prices", count_footballers)

    first, second = bot.fpl.requests
    assert "If-None-Match" not in first.headers
    assert second.headers["If-None-Match"] == '"v1"'
    assert seen == [3, 3]


async def test_bootstrap_static_is_reused_for_15_minutes_then_refetched(bot: BotHarness) -> None:
    await bot.run_job("lookup", read_bootstrap)
    await bot.advance(timedelta(minutes=14, seconds=59))
    await bot.run_job("lookup", read_bootstrap)
    reused = list(bot.fpl.requested_paths)

    await bot.advance(timedelta(minutes=1))
    await bot.run_job("lookup", read_bootstrap)

    assert reused == ["bootstrap-static"]
    assert bot.fpl.requested_paths == ["bootstrap-static", "bootstrap-static"]


async def test_bootstrap_static_with_missing_fields_fails_the_job(bot: BotHarness) -> None:
    bot.fpl.respond("bootstrap-static/", canned_fpl_response("bootstrap-static-missing-fields"))

    first = await bot.run_job("prices", read_bootstrap)
    second = await bot.run_job("prices", read_bootstrap)

    assert (first, second) == (False, False)
    assert bot.owner.replies == [
        "FPL-BAD-DATA: the prices job failed. FPL answered without the fields we need."
    ]


async def test_raw_fpl_responses_are_never_written_to_the_database(bot: BotHarness) -> None:
    await bot.owner.send("/invite")
    await bot.run_job("prices", read_bootstrap)

    stored = await bot.database_text()

    for raw in ["Fakesson", "Northbridge", "Gameweek 2", "element_types"]:
        assert raw not in stored


async def read_bootstrap(fpl: FplSource) -> None:
    await fpl.bootstrap_static()
