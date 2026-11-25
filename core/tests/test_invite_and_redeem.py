"""Ticket 26: the owner invites a friend, the friend redeems the link, strangers get silence."""

from datetime import timedelta

from tests.harness import OWNER_ID, SENDER_NAME, BotHarness, start_code_in

GREETING = (
    "Welcome! I give FPL advice. I never ask for your FPL password, "
    "and you make every change yourself."
)
ASK_TEAM_ID = (
    "Send me your FPL team ID.\n"
    "You can find it in the address bar on the FPL site, in the number after /entry/ "
    "(open the Points tab)."
)
# Redeeming greets the friend and starts setup (ticket 28).
WELCOMED = [GREETING, ASK_TEAM_ID]


async def test_invited_friend_is_greeted_when_opening_the_owners_link(bot: BotHarness) -> None:
    await bot.owner.send("/invite")
    code = start_code_in(bot.owner.last_reply)

    friend = bot.private_chat(user_id=2001)
    await friend.send(f"/start {code}")

    assert friend.replies == WELCOMED


async def test_a_used_code_is_refused_with_a_short_reply(bot: BotHarness) -> None:
    code = await invite(bot)
    await bot.private_chat(user_id=2001).send(f"/start {code}")

    latecomer = bot.private_chat(user_id=2002)
    await latecomer.send(f"/start {code}")

    assert latecomer.replies == [
        "That invite code has already been used. Ask the owner for a new one."
    ]


async def test_a_code_expires_48_hours_after_it_was_issued(bot: BotHarness) -> None:
    on_time_code = await invite(bot)
    late_code = await invite(bot)
    await bot.advance(timedelta(hours=47, minutes=59))
    on_time = bot.private_chat(user_id=2001)
    await on_time.send(f"/start {on_time_code}")

    await bot.advance(timedelta(minutes=1))
    late = bot.private_chat(user_id=2002)
    await late.send(f"/start {late_code}")

    assert on_time.replies == WELCOMED
    assert late.replies == ["That invite code has expired. Ask the owner for a new one."]


async def test_a_valid_code_is_refused_once_ten_members_have_joined(bot: BotHarness) -> None:
    for user_id in range(2001, 2011):
        await bot.private_chat(user_id).send(f"/start {await invite(bot)}")
    code = await invite(bot)

    eleventh = bot.private_chat(user_id=2011)
    await eleventh.send(f"/start {code}")

    assert eleventh.replies == ["Sorry, this bot is full (10 Members)."]


async def test_strangers_get_no_reply_to_anything(bot: BotHarness) -> None:
    await invite(bot)
    stranger = bot.private_chat(user_id=6666)

    for text in ["hello", "/start", "/start NEVER-ISSUED-CODE", "/invite", "/help"]:
        await stranger.send(text)

    assert stranger.replies == []


async def test_group_chats_are_ignored_entirely(bot: BotHarness) -> None:
    group = bot.group_chat(chat_id=-100500, user_id=2001)
    owner_in_group = bot.group_chat(chat_id=-100500, user_id=bot.owner.user_id)
    code = await invite(bot)

    await owner_in_group.send("/invite")
    await group.send(f"/start {code}")
    friend = bot.private_chat(user_id=2001)
    await friend.send(f"/start {code}")

    assert group.replies == []
    assert friend.replies == WELCOMED


async def test_a_member_opening_another_link_does_not_use_it_up(bot: BotHarness) -> None:
    member = bot.private_chat(user_id=2001)
    await member.send(f"/start {await invite(bot)}")
    spare_code = await invite(bot)

    await member.send(f"/start {spare_code}")
    newcomer = bot.private_chat(user_id=2002)
    await newcomer.send(f"/start {spare_code}")

    assert member.replies == [*WELCOMED, ASK_TEAM_ID]
    assert newcomer.replies == WELCOMED


async def test_wrong_code_attempts_are_rate_limited_per_chat(bot: BotHarness) -> None:
    code = await invite(bot)
    guesser = bot.private_chat(user_id=6666)
    for attempt in range(5):
        await guesser.send(f"/start WRONG-GUESS-{attempt}")

    await guesser.send(f"/start {code}")
    locked_out = list(guesser.replies)
    await bot.advance(timedelta(hours=1))
    await guesser.send(f"/start {code}")

    assert locked_out == []
    assert guesser.replies == WELCOMED


async def test_one_chats_wrong_codes_do_not_lock_out_another(bot: BotHarness) -> None:
    code = await invite(bot)
    for attempt in range(5):
        await bot.private_chat(user_id=6666).send(f"/start WRONG-GUESS-{attempt}")

    friend = bot.private_chat(user_id=2001)
    await friend.send(f"/start {code}")

    assert friend.replies == WELCOMED


async def test_invite_codes_are_long_random_and_never_stored_in_clear(bot: BotHarness) -> None:
    codes = [await invite(bot) for _ in range(20)]
    await bot.private_chat(user_id=2001).send(f"/start {codes[0]}")

    stored = await bot.database_text()

    assert len(set(codes)) == len(codes)
    # 64 bits need at least 11 characters of the 64-symbol URL-safe alphabet.
    assert all(len(code) >= 11 for code in codes)
    assert not [code for code in codes if code in stored]


async def test_logs_name_members_by_internal_number_only(bot: BotHarness) -> None:
    code = await invite(bot)
    friend = bot.private_chat(user_id=7_654_321)
    await friend.send(f"/start {code}")
    await friend.send("/start")

    log_text = "\n".join(bot.logs)

    assert "member 1 " in log_text
    for identifier in ["7654321", str(OWNER_ID), code, SENDER_NAME]:
        assert identifier not in log_text


async def invite(bot: BotHarness) -> str:
    await bot.owner.send("/invite")
    return start_code_in(bot.owner.last_reply)
