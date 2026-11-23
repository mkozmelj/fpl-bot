"""Fixed message templates. All user-facing wording lives here."""

GREETING = (
    "Welcome! I give FPL advice. I never ask for your FPL password, "
    "and you make every change yourself."
)
WELCOME_BACK = "Welcome back."

INVITE_USED = "That invite code has already been used. Ask the owner for a new one."
INVITE_EXPIRED = "That invite code has expired. Ask the owner for a new one."


def bot_full(member_cap: int) -> str:
    return f"Sorry, this bot is full ({member_cap} Members)."


def invite_link(bot_username: str, code: str, valid_hours: int) -> str:
    return (
        f"Invite link (single use, expires in {valid_hours} hours):\n"
        f"https://t.me/{bot_username}?start={code}"
    )
