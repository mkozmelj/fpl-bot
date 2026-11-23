"""Ticket 29: the Watch list (``/watch``, ``/watch add``, ``/watch remove``).

Mirrors the "Ambiguous Watch list" walkthrough of the approved prototype (ticket 14), with
synthetic Footballers: "Aurelio" matches two of them, as "Gabriel" does in the prototype.
"""

import json
from typing import Any

from fplbot.sources.fpl import FplResponse
from tests.harness import BotHarness

# (id, first name, second name, web name, position id, club id, price in tenths)
FOOTBALLERS = [
    (11, "Mo", "Varenne", "Varenne", 3, 1, 132),
    (12, "Erling", "Thorsby", "Thorsby", 4, 2, 151),
    (13, "Aurelio", "Brandt Okafor", "Aurelio", 2, 1, 61),
    (14, "Aurelio", "de Mensah", "A.Mensah", 4, 1, 70),
    (15, "Kit", "Quillon", "Quillon", 1, 2, 45),
    (16, "José", "Ñúñez Pérez", "Núñez", 3, 2, 100),
]


def bootstrap(footballers: list[tuple[int, str, str, str, int, int, int]]) -> FplResponse:
    data: dict[str, Any] = {
        "events": [],
        "teams": [
            {"id": 1, "name": "Northbridge", "short_name": "NOR"},
            {"id": 2, "name": "Southport Rovers", "short_name": "SOU"},
        ],
        "element_types": [
            {"id": 1, "singular_name_short": "GKP"},
            {"id": 2, "singular_name_short": "DEF"},
            {"id": 3, "singular_name_short": "MID"},
            {"id": 4, "singular_name_short": "FWD"},
        ],
        "elements": [
            {
                "id": id_,
                "first_name": first,
                "second_name": second,
                "web_name": web,
                "element_type": position,
                "team": club,
                "now_cost": cost,
                "status": "a",
            }
            for id_, first, second, web, position, club, cost in footballers
        ],
    }
    return FplResponse(200, json.dumps(data).encode())


async def member(bot: BotHarness) -> Any:
    bot.fpl.respond("bootstrap-static/", bootstrap(FOOTBALLERS))
    return await bot.active_member(user_id=2001, team_id=1001)


async def test_adding_a_single_match_confirms_with_club_position_and_price(
    bot: BotHarness,
) -> None:
    alice = await member(bot)

    await alice.send("/watch add varenne")

    assert alice.last_reply == (
        "Added Varenne (NOR, MID) at £13.2m. I'll flag him in the Price alert if he may rise."
    )


async def test_ambiguous_watch_list_walkthrough(bot: BotHarness) -> None:
    alice = await member(bot)

    await alice.send("/watch add aurelio")
    assert alice.last_reply == 'Several Footballers match "aurelio". Which one?'
    assert alice.last_message.buttons == ["Aurelio (NOR, DEF)", "A.Mensah (NOR, FWD)"]

    await alice.press("A.Mensah (NOR, FWD)")
    assert alice.last_reply == (
        "Added A.Mensah (NOR, FWD) at £7.0m. I'll flag him in the Price alert if he may rise."
    )

    await alice.send("/watch add mensah")
    assert alice.last_reply == "A.Mensah is already on your Watch list."

    await alice.send("/watch add nobody")
    assert alice.last_reply == 'No Footballer matches "nobody".'

    await alice.send("/watch")
    assert alice.last_reply == (
        "Your Watch list:\n"
        "A.Mensah (NOR, FWD) £7.0m\n"
        "\n"
        "I will tell you in the Price alert if any may rise."
    )

    await alice.send("/watch remove mensah")
    assert alice.last_reply == "Removed A.Mensah."
    await alice.send("/watch")
    assert alice.last_reply == "Your Watch list is empty. Try /watch add Salah"


async def test_the_list_shows_every_footballer_in_the_order_added(bot: BotHarness) -> None:
    alice = await member(bot)

    for name in ["quillon", "nunez", "thorsby"]:
        await alice.send(f"/watch add {name}")
    await alice.send("/watch")

    assert alice.last_reply == (
        "Your Watch list:\n"
        "Quillon (SOU, GKP) £4.5m\n"
        "Núñez (SOU, MID) £10.0m\n"
        "Thorsby (SOU, FWD) £15.1m\n"
        "\n"
        "I will tell you in the Price alert if any may rise."
    )


async def test_names_match_whatever_case_accents_or_part_of_the_name_is_typed(
    bot: BotHarness,
) -> None:
    alice = await member(bot)

    await alice.send("/watch add NÚÑEZ")
    by_accent = alice.last_reply
    await alice.send("/watch add erling thor")
    by_full_name = alice.last_reply
    await alice.send("/watch add arenn")
    by_part = alice.last_reply

    assert by_accent.startswith("Added Núñez (SOU, MID) at £10.0m.")
    assert by_full_name.startswith("Added Thorsby (SOU, FWD) at £15.1m.")
    assert by_part.startswith("Added Varenne (NOR, MID) at £13.2m.")


async def test_a_stale_pick_button_changes_nothing(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/watch add aurelio")
    question = alice.last_message
    await alice.press("Aurelio (NOR, DEF)")

    await alice.press("A.Mensah (NOR, FWD)", on=question)
    tapped_twice = alice.last_reply
    await alice.send("/watch add aurelio")
    second_question = alice.last_message
    await alice.send("/settings")
    await alice.press("A.Mensah (NOR, FWD)", on=second_question)
    after_a_command = alice.last_reply
    await alice.send("/watch")

    stale = "That button is out of date. Send /help to see what you can do."
    assert tapped_twice == stale
    assert after_a_command == stale
    assert alice.last_reply.startswith("Your Watch list:\nAurelio (NOR, DEF) £6.1m\n\n")


async def test_a_21st_footballer_is_refused(bot: BotHarness) -> None:
    squad = [(100 + n, "", f"Synthfield{n:02d}", f"Synthfield{n:02d}", 3, 1, 50) for n in range(21)]
    bot.fpl.respond("bootstrap-static/", bootstrap(squad))
    alice = await bot.active_member(user_id=2001, team_id=1001)
    for n in range(20):
        await alice.send(f"/watch add synthfield{n:02d}")
    assert alice.last_reply.startswith("Added Synthfield19")

    await alice.send("/watch add synthfield20")
    full = alice.last_reply
    await alice.send("/watch")

    assert full == "Your Watch list is full (20). Remove someone first."
    assert "Synthfield19" in alice.last_reply
    assert "Synthfield20" not in alice.last_reply


async def test_removing_a_footballer_who_is_not_on_the_list(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/watch remove varenne")
    from_empty = alice.last_reply
    await alice.send("/watch add varenne")

    await alice.send("/watch remove thorsby")
    not_there = alice.last_reply
    await alice.send("/watch")

    assert from_empty == '"varenne" isn\'t on your Watch list.'
    assert not_there == '"thorsby" isn\'t on your Watch list.'
    assert "Varenne (NOR, MID)" in alice.last_reply


async def test_unclear_watch_commands_explain_the_usage(bot: BotHarness) -> None:
    alice = await member(bot)

    for command in ["/watch add", "/watch remove", "/watch frobnicate salah"]:
        await alice.send(command)
        assert alice.last_reply == "Use /watch, /watch add <name> or /watch remove <name>."


async def test_too_many_matches_ask_for_more_of_the_name(bot: BotHarness) -> None:
    many = [(200 + n, "", f"Twinfield{n}", f"Twinfield{n}", 2, 2, 40) for n in range(9)]
    bot.fpl.respond("bootstrap-static/", bootstrap(many))
    alice = await bot.active_member(user_id=2001, team_id=1001)

    await alice.send("/watch add twin")

    assert alice.last_reply == '9 Footballers match "twin". Type more of the name.'
    assert alice.last_message.buttons == []


async def test_fpl_being_unreachable_is_explained(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/watch add varenne")
    bot.fpl.respond("bootstrap-static/", FplResponse(503, b"The game is being updated."))

    await alice.send("/watch add thorsby")
    adding = alice.last_reply
    await alice.send("/watch")
    listing = alice.last_reply

    unreachable = "I can't reach FPL right now. Try again in a few minutes."
    assert adding == unreachable
    assert listing == unreachable


async def test_settings_and_help_show_the_watch_list(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/settings")
    empty = alice.last_reply
    await alice.send("/watch add varenne")
    await alice.send("/watch add quillon")
    await alice.send("/settings")
    listed = alice.last_reply
    await alice.send("/help")

    assert empty.endswith("\nWatch list: empty")
    assert listed.endswith("\nWatch list: Varenne, Quillon")
    assert alice.last_reply.startswith(
        "/watch  show your Watch list\n/watch add <name>\n/watch remove <name>\n/goal"
    )


async def test_watch_list_rows_go_when_the_member_leaves(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/watch add varenne")
    assert "watch_list:" in await bot.database_text()

    await alice.send("/leave")
    await alice.press("Delete my data")

    assert "watch_list:" not in await bot.database_text()


async def test_logs_never_name_the_member_or_the_footballer(bot: BotHarness) -> None:
    alice = await member(bot)
    await alice.send("/watch add varenne")
    await alice.send("/watch remove varenne")

    log_text = "\n".join(bot.logs)

    assert "member 1 added a Footballer to their Watch list" in log_text
    assert "member 1 removed a Footballer from their Watch list" in log_text
    assert "Varenne" not in log_text
    assert "2001" not in log_text
