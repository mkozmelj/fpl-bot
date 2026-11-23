"""Fixed message templates. All user-facing wording lives here."""

from datetime import datetime

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


# Owner incident DMs: a fixed code and the job name only, never a stack trace or Member details.
_INCIDENT_HINTS = {
    "FPL-403": "FPL refused access (403). Not retried; the job waits for its next run.",
    "FPL-DOWN": "FPL kept failing (429/5xx) after 5 tries.",
    "FPL-UPDATING": "FPL says the game is being updated.",
    "FPL-HTTP": "FPL answered with an unexpected status.",
    "FPL-BAD-DATA": "FPL answered without the fields we need.",
    "JOB-ERROR": "Unexpected error; see the logs.",
}


def owner_alert(code: str, job: str) -> str:
    hint = _INCIDENT_HINTS.get(code, "")
    return f"{code}: the {job} job failed. {hint}".rstrip()


def owner_reminder(code: str, job: str, since: datetime) -> str:
    return f"{code}: the {job} job is still failing (since {since:%d %b %H:%M} UTC)."


def owner_recovered(code: str, job: str) -> str:
    return f"{code}: the {job} job has recovered."
