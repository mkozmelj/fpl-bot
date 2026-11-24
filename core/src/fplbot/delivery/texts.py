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


# --- Nightly Member backup (ticket 39) ---


def member_backup_caption(taken_at: datetime, members: int) -> str:
    noun = "Member" if members == 1 else "Members"
    return (
        f"Member backup, {taken_at:%d %b %Y %H:%M} UTC: {members} {noun}. Encrypted with age; "
        "the restore drill is in docs/runbook-secrets.md."
    )


MEMBER_BACKUP_NO_KEY = (
    "Member backup skipped: BACKUP_AGE_PUBLIC_KEY is not set. Set it to an age public key to get "
    "a nightly encrypted backup here (docs/runbook-secrets.md)."
)


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
    ("/squad", "your Squad at the last deadline"),
    ("/watch", "show your Watch list"),
    ("/watch add <name>", ""),
    ("/watch remove <name>", ""),
    ("/goal", "switch Goal"),
    ("/time HH:MM", "Price alert time"),
    ("/tz", "change timezone"),
    ("/settings", "show everything I know about you"),
    ("/leave", "delete your data and leave"),
]


def help_text() -> str:
    return "\n".join(f"{command}  {what}".rstrip() for command, what in COMMANDS)


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


# --- /squad (ticket 30) ---

NO_DEADLINE_YET = "The season hasn't started yet: there's no Squad from a deadline to show."


def squad(
    team_name: str,
    gameweek: int,
    lines: list[tuple[str, list[str]]],
    bench: list[str],
    hidden_note: str | None,
) -> str:
    """``lines``: (position, names) for the XI in position order; names carry (C)/(VC)."""
    xi = "\n".join(f"{position}  {', '.join(names)}" for position, names in lines)
    text = f"{team_name} · your Squad at the GW{gameweek} deadline\n{xi}\nBench: {', '.join(bench)}"
    return f"{text}\n\n{hidden_note}" if hidden_note else text


def captain(name: str) -> str:
    return f"{name} (C)"


def vice_captain(name: str) -> str:
    return f"{name} (VC)"


def picks_hidden(next_gameweek: int, local_deadline: str, last_gameweek: int) -> str:
    return (
        f"FPL hides GW{next_gameweek} picks until the deadline ({local_deadline} your time), so "
        f"changes you've made since GW{last_gameweek} don't show yet."
    )


def no_squad(gameweek: int, hidden_note: str | None) -> str:
    text = (
        f"I don't have your Squad from the GW{gameweek} deadline: FPL isn't showing those picks. "
        "Try /squad again later."
    )
    return f"{text}\n\n{hidden_note}" if hidden_note else text


# --- Watch list (ticket 29; wording from the ticket 14 prototype) ---

WATCH_USAGE = "Use /watch, /watch add <name> or /watch remove <name>."
WATCH_EMPTY = "Your Watch list is empty. Try /watch add Salah"
WATCH_FULL = "Your Watch list is full (20). Remove someone first."


def watch_line(name: str, club: str, position: str, price: str) -> str:
    return f"{name} ({club}, {position}) {price}"


def watch_list(lines: list[str]) -> str:
    listed = "\n".join(lines)
    return f"Your Watch list:\n{listed}\n\nI will tell you in the Price alert if any may rise."


def watch_choice(name: str, club: str, position: str) -> str:
    return f"{name} ({club}, {position})"


def watch_ambiguous(typed: str) -> str:
    return f'Several Footballers match "{typed}". Which one?'


def watch_too_many(count: int, typed: str) -> str:
    return f'{count} Footballers match "{typed}". Type more of the name.'


def watch_no_match(typed: str) -> str:
    return f'No Footballer matches "{typed}".'


def watch_already(name: str) -> str:
    return f"{name} is already on your Watch list."


def watch_added(name: str, club: str, position: str, price: str) -> str:
    return (
        f"Added {name} ({club}, {position}) at {price}. "
        "I'll flag him in the Price alert if he may rise."
    )


def watch_not_there(typed: str) -> str:
    return f'"{typed}" isn\'t on your Watch list.'


def watch_removed(name: str) -> str:
    return f"Removed {name}."


def price_alert_header(gameweek: int) -> str:
    return f"Price alert · GW{gameweek} · tonight 00:00 UK"


PRICE_FALLS = "Likely to fall (you own)"
PRICE_RISES = "Likely to rise (Watch list)"
VERY_LIKELY = "Very likely"
LIKELY = "Likely"


def price_alert_line(
    name: str, position: str, club: str, price: str, new_price: str, likelihood: str
) -> str:
    return f"• {name} {position} {club} {price} → {new_price} · {likelihood}"


def price_alert_tomorrow(mentions: list[tuple[str, bool]]) -> str:
    """``mentions``: (name, rise) pairs."""
    listed = ", ".join(f"{name} to {'rise' if rise else 'fall'}" for name, rise in mentions)
    return f"Tomorrow night (Very likely): {listed}."


PRICE_SAVING_FALLS = "If you were planning to sell anyway, doing it before 00:00 UK saves £0.1m."
PRICE_SAVING_RISES = (
    "If you were planning to buy anyway, doing it before 00:00 UK avoids paying £0.1m more."
)
PRICE_SAVING_BOTH = (
    "If you were planning to sell or buy anyway, doing it before 00:00 UK saves £0.1m a Footballer."
)
PRICE_STALE_SQUAD = "Based on your Squad at the last deadline. Ignore any you've already sold."


def price_alert_failed(code: str, job: str) -> str:
    return f"{owner_alert(code, job)} Tonight's Price alerts were not sent."


# --- /accuracy (ticket 37): owner only ---

ACCURACY_EMPTY = (
    "Price predictor accuracy: nothing scored yet. A night's codes are scored once its 00:10 "
    "price-change archive is stored."
)
ACCURACY_HIT = "A hit: a + code rose, a - code fell, 0 stayed."
ACCURACY_TOTAL = "All"
ACCURACY_MANUAL = "Raise the alert threshold by hand if it persists; nothing changes by itself."


def accuracy_header(season: str) -> str:
    return f"Price predictor accuracy · {season}"


def accuracy_section(tomorrow: bool, nights: int) -> str:
    horizon = "Tomorrow night's code" if tomorrow else "Tonight's code"
    return f"{horizon} · last {nights} nights · season"


def accuracy_line(code: str, recent: str, season: str) -> str:
    return f"{code}  {recent} · {season}"


def accuracy_tally(hits: int, predictions: int, percent: int | None) -> str:
    return "no data" if percent is None else f"{hits}/{predictions} {percent}%"


def accuracy_floors_met(nights: int, minimum: int) -> str:
    return f"Floors (±4 70%, ±5 85%; last {nights} nights, {minimum}+ predictions a code): all met."


def accuracy_breach(tomorrow: bool, code: str, tally: str, floor: int) -> str:
    horizon = "tomorrow night's" if tomorrow else "tonight's"
    return f"Below floor: {horizon} {code} at {tally} (floor {floor}%)."


def settings_watch_list(names: list[str] | None, count: int) -> str:
    """The /settings line. ``names`` is ``None`` when FPL can't be reached for them."""
    if count == 0:
        return "Watch list: empty"
    if names is None:
        return f"Watch list: {count} Footballers"
    return "Watch list: " + ", ".join(names)


# --- Owner /status, startup and usage warnings (ticket 38) ---

STATUS_TITLE = "Status"
STATUS_COMPLETIONS = "Last completed:"
NEON_REACHABLE = "Neon: reachable"
NEON_UNREACHABLE = "Neon: unreachable"
COMPUTE_HOURS_UNREADABLE = (
    "Compute hours: not readable without a Neon API key; see the Neon console."
)


def deploy_version(version: str, sha: str) -> str:
    return f"v{version} ({sha[:7]})"


def status_uptime(uptime: str, version: str) -> str:
    return f"Up {uptime} · {version}"


def status_completion(job: str, period: str | None, at: datetime | None) -> str:
    if period is None or at is None:
        return f"• {job}: never"
    return f"• {job}: {period}, {at:%d %b %H:%M} UTC"


def status_completion_unknown(job: str) -> str:
    return f"• {job}: unknown"


def database_size(size_mb: float, limit_mb: int, percent: int) -> str:
    return f"Database size: {size_mb:.1f} MB of {limit_mb} MB ({percent}%)"


def online(version: str) -> str:
    return f"online {version}"


def storage_warning(size_mb: float, limit_mb: int, percent: int) -> str:
    return (
        f"Neon storage is at {percent}% ({size_mb:.1f} MB of {limit_mb} MB). Check which tables "
        "grew before the next Gameweek (docs/runbook-secrets.md, Monthly Neon check)."
    )
