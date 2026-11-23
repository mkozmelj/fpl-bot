"""Fixed message templates. All user-facing wording lives here."""

from datetime import datetime

GREETING = (
    "Welcome! I give FPL advice. I never ask for your FPL password, "
    "and you make every change yourself."
)

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


# --- Setup, settings and leaving (ticket 28; wording from the ticket 14 prototype) ---

ASK_TEAM_ID = (
    "Send me your FPL team ID.\n"
    "You can find it in the address bar on the FPL site, in the number after /entry/ "
    "(open the Points tab)."
)
NOT_A_TEAM_ID = "That doesn't look like a team ID. It's just digits, like 1234567."
TEAM_TAKEN = "That team is already linked to another Member. If that is a mistake, ask the owner."
FPL_UNREACHABLE = "I can't reach FPL right now. Try again in a few minutes."
CONFIRM_YES = "Yes, that's me"
CONFIRM_NO = "No, wrong team"
WRONG_TEAM = "No problem. Send the correct team ID."

ASK_GOAL = (
    "What should my advice aim for?\n"
    "• Overall rank (the default)\n"
    "• Mini-league: stay ahead of the Rivals in one league\n"
    "You can switch any time with /goal."
)
GOAL_OVERALL = "Overall rank"
GOAL_LEAGUE = "Mini-league"
ASK_LEAGUE = "Which mini-league?"
NO_MINI_LEAGUE = (
    "You're not in any private mini-league yet, so I've set your Goal to Overall rank. "
    "Switch with /goal once you join one."
)

TZ_OTHER = "Other…"
ASK_TZ_TEXT = "Type your city or timezone (for example Ljubljana or Europe/Berlin)."

FINISH_SETUP_FIRST = "Let's finish setting you up first."
STALE_BUTTON = "That button is out of date. Send /help to see what you can do."
NOT_UNDERSTOOD = "I didn't catch that. /help shows what I can do."
UNKNOWN_COMMAND = "I don't know that command. /help shows what I can do."
CANCELLED = "Okay, cancelled."
TIME_FORMAT = "Use 24-hour time, like /time 19:30."

ASK_LEAVE = (
    "This deletes everything I store about you: your team ID, Goal, Watch list, timezone and "
    "chat ID. Your invite code cannot be reused. Continue?"
)
LEAVE_YES = "Delete my data"
LEAVE_NO = "Keep me"
LEAVE_KEPT = "Okay, nothing deleted."
LEFT = "Done. Everything I stored about you is deleted. To rejoin you need a new invite."

# (command, what it does) in /help order. Later tickets add their commands here.
COMMANDS: list[tuple[str, str]] = [
    ("/goal", "switch Goal"),
    ("/time HH:MM", "Price alert time"),
    ("/tz", "change timezone"),
    ("/settings", "show everything I know about you"),
    ("/leave", "delete your data and leave"),
]


def help_text() -> str:
    return "\n".join(f"{command}  {what}" for command, what in COMMANDS)


def unknown_team(team_id: str) -> str:
    return f"I couldn't find an FPL team with ID {team_id}. Check the number and send it again."


def confirm_team(team_name: str, manager: str, overall_rank: int | None) -> str:
    rank = f"overall rank {overall_rank:,}" if overall_rank else "no overall rank yet"
    return f'Found "{team_name}", managed by {manager}, {rank}.\nIs that you?'


def ask_tz(alert_time: str) -> str:
    return (
        f"Which timezone are you in? Your nightly Price alert goes out at {alert_time} your "
        "time (change it with /time)."
    )


def unknown_timezone(typed: str) -> str:
    return (
        f'I don\'t know "{typed}". Try a city (Ljubljana, Sydney…) '
        "or a zone name like Europe/Berlin."
    )


def goal_league(league_name: str) -> str:
    return f"Mini-league: {league_name}"


def summary(team: str, goal: str, timezone: str, alert_time: str) -> str:
    return (
        f"Team: {team}\n"
        f"Goal: {goal}\n"
        f"Timezone: {timezone}\n"
        f"Price alert: {alert_time} your time, only on nights with something to report"
    )


def all_set(team_name: str, summary_text: str) -> str:
    return f"You're all set, {team_name}.\n\n{summary_text}\n\nCommands:\n{help_text()}"


def saved(summary_text: str) -> str:
    return f"Saved.\n\n{summary_text}"


def welcome_back(team_name: str) -> str:
    return f"Welcome back, {team_name}.\n\n{help_text()}"


def alert_time_set(alert_time: str, timezone: str) -> str:
    return f"Done. Price alerts at {alert_time} {timezone} time."


def alert_time_clamped(alert_time: str, timezone: str, send_uk: str, send_local: str) -> str:
    return (
        f"{alert_time_set(alert_time, timezone)}\n"
        "Price alerts only go out between 17:00 and 23:15 UK time, so yours will arrive at "
        f"{send_uk} UK ({send_local} your time)."
    )
