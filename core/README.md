# fplbot (core)

The Python bot: one asyncio process with Telegram long polling, Postgres via SQLAlchemy 2.0 async
(psycopg 3) and Alembic. Architecture and decisions: `.scratch/fpl-bot/issues/12-*.md`, the
Phase 1 spec `25-spec-phase-1.md` and `docs/adr/`. Vocabulary: `GLOSSARY.md`.

## Layout

```
core/
  pyproject.toml, uv.lock        uv project (Python 3.14, hashed lockfile)
  alembic.ini                    for the `alembic` CLI; URL comes from DATABASE_URL
  src/fplbot/
    __main__.py                  `python -m fplbot [migrate]`
    app.py                       composition root (FplBotApp): config + swappable edges
    config.py                    environment config
    clock.py                     Clock protocol (now, sleep) + SystemClock
    logs.py                      logging setup (no identifiers in logs)
    sources/                     FPL adapter: fpl.py (FplSource -> PoliteFplClient ->
                                 FplTransport), limiter.py (shared 1 req/s, Priority),
                                 live.py (httpx), fake.py (recorded fixtures)
    store/                       schema.py, migrations/ (Alembic), members.py, seasons.py, db.py
    prediction/ optimisation/    Phase 2/3, empty
    advice/                      pure decisions (Gaps, Rivals, Price alert)
    explain/                     Phase 2, empty
    delivery/                    telegram.py (PTB wiring), conversation.py (text in, replies out),
                                 texts.py (all wording), rate_limit.py,
                                 owner_alerts.py (deduplicated owner incident DMs)
    jobs/                        runner.py (JobRunner: runs a job, reports outcome to the
                                 owner), scheduler.py (planner registry, no persisted
                                 store), post_deadline.py (picks job, deadline refreshes,
                                 startup catch-up), backfill.py (join backfill),
                                 followed_leagues.py (Followed-league recompute),
                                 gameweek_final.py (gw-final job)
  tests/
    harness.py                   THE test seam (see below)
    conftest.py                  throwaway database + `bot` fixture
    fixtures/fpl/                synthetic FPL API fixtures, mirroring API paths
```

Dependency direction: `delivery -> advice -> prediction/optimisation -> store -> sources`, with
`jobs` orchestrating all of them. Only `delivery` knows about chats.

## Running locally

The quickest path is the root `README.md`: copy `.env.example` to `.env` and start the
docker-compose Postgres (`docker compose up -d` from the repo root). The variables, by hand:

```sh
cd core
uv sync
export TELEGRAM_BOT_TOKEN=...       # from BotFather
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fplbot
export OWNER_TELEGRAM_ID=...        # your numeric Telegram user ID
export FPL_SOURCE=fake              # serve tests/fixtures/fpl instead of calling FPL
uv run python -m fplbot migrate     # alembic upgrade head
uv run python -m fplbot             # long-poll Telegram; Ctrl-C to stop
```

Optional: `FPL_FIXTURES_DIR` points the fake source at another fixture directory.
`BACKUP_AGE_PUBLIC_KEY` (an `age1...` public key) turns on the nightly encrypted Member backup
to the owner's chat; unset, the owner is told once that backups are off.
`FPL_SOURCE=live` (the default) calls the real FPL API through the polite client: at most 1
request a second, a generic browser User-Agent, backoff on 429/5xx, never a retry on 403.

## Tests, lint, types

```sh
cd core
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:54329/postgres  # admin URL
uv run pytest
uv run ruff format --check . && uv run ruff check .
uv run pyright
```

`TEST_DATABASE_URL` is an admin URL for a throwaway Postgres server. Each test session creates a
uniquely named database (`fplbot_test_<pid>_<random>`), migrates it with Alembic, empties every
table before each test, and drops the database at the end. No secrets are needed.

## The test seam

Every behaviour test goes through `tests/harness.py`, which runs the real `FplBotApp` (the real
python-telegram-bot `Application`, real Postgres) with three fakes swapped in at the edges:

| Fake | Replaces | Use in a test |
|---|---|---|
| `FakeClock` | `SystemClock` | `await bot.advance(timedelta(hours=49))` |
| `FakeTelegram` | PTB's HTTP request layer | `chat.replies`, `chat.last_reply`, `bot.telegram.calls` |
| `FakeFplTransport` | the live FPL HTTP transport | `bot.fpl.respond(path, FplResponse(403))`, `bot.fpl.requested_paths`, `bot.fpl.requests` (time, path, headers) |

```python
async def test_example(bot: BotHarness) -> None:
    await bot.owner.send("/invite")
    code = start_code_in(bot.owner.last_reply)
    friend = bot.private_chat(user_id=2001)
    await friend.send(f"/start {code}")
    assert friend.replies == ["Welcome! ..."]
```

Helpers: `bot.owner`, `bot.private_chat(user_id)`, `bot.group_chat(chat_id, user_id)`,
`chat.send(text)` (feeds a Telegram update and waits for it to be handled), `bot.advance(delta)`,
`bot.logs` (captured log lines), `await bot.database_text()` (every row as text, for "is X
stored?" checks). Assert only on what chats receive, log lines and externally meaningful rows.
Never on module calls, SQL or internal state.

Jobs and time: `bot.run_job(name, job, priority)` runs a job through the bot's `JobRunner`
(outcome reported to the owner as in production) and returns `True` on success;
`bot.start_job(...)` starts one in the background. A job is `async def job(fpl: FplSource)`.

All waiting in the bot goes through `Clock.sleep` (rate limit, backoff, scheduled waits), so it
runs in simulated time: `bot.advance(delta)` wakes every sleeper due within `delta` in order, and
`chat.send` / `bot.run_job` move time on by themselves whenever the work they wait for is asleep.
Never wait on a bare `asyncio.Event` or `asyncio.sleep` for time-based behaviour: the harness
cannot see it and reports "the bot did not settle".

Buttons: `chat.last_message.buttons` (labels), `await chat.press(label)` (taps it on the latest
message offering it; `on=message` taps an older, stale keyboard). Shortcuts:
`await bot.invited_friend(user_id)` (redeemed, setup not started) and
`await bot.active_member(user_id, team_id, timezone)` (set up through the real flow; the team
needs a fixture under `fixtures/fpl/entry/`). `await bot.restart()` starts a fresh process on
the same database and fakes, to test what survives in memory.

Scheduled jobs: `await bot.start_scheduling()` starts the bot's scheduler as production does at
startup (startup refresh and catch-up, then the plan); from then on `bot.advance(delta)` fires
due jobs in simulated time, and `bot.restart()` keeps scheduling on. It is off by default so tests
that script FPL answers are not disturbed by scheduled fetches. A feature adds its jobs by
registering a planner (`app.scheduler.add`, see `jobs/scheduler.py`).
`FakeTelegram._result` answers Bot API methods; add a case when the bot starts calling a new
method whose result it reads.

## FPL fixtures

`tests/fixtures/fpl/` mirrors API paths: `bootstrap-static/` is served from
`bootstrap-static.json`, `entry/1001/event/11/picks/` from `entry/1001/event/11/picks.json`. A
path without a file answers 404. Script awkward answers per test with
`bot.fpl.respond("bootstrap-static/", FplResponse(503, b'"The game is being updated."'))`;
several responses are served in order and the last one repeats.

Recorded awkward answers live in `tests/fixtures/fpl-responses/` (status, headers, body):
`canned_fpl_response("503-updating" | "403-forbidden" | "429-retry-after" | "502-bad-gateway" |
"bootstrap-static-missing-fields")`. `fpl_fixture("bootstrap-static/")` gives the normal 200
answer for a path, to script "fails, then recovers".

The default fixtures match the harness clock (Thu 19 Nov 2026): `bootstrap-static.json` has
GW1-12 with GW10 the last deadline and GW11 the next (Sat 21 Nov 11:00 UTC), and `fixtures.json`
a few fixtures. Team 1001 has `history.json` (GW9-10) and picks for GW9 and GW10; team 1002 has
history for GW10 but no picks (FPL's 404, "hidden"); team 1003 has no history.

Linking a team starts the join backfill as a background job at routine priority, so a test that
needs the Member's Squad lets time pass first (`await bot.advance(timedelta(minutes=1))`).

Fixtures are small and synthetic (made-up clubs and Footballers). Never commit real FPL data.

## Migrations

Add a revision under `src/fplbot/store/migrations/versions/` (hand-written or
`DATABASE_URL=... uv run alembic revision --autogenerate -m "..."`), update `store/schema.py`, and
give every new table a `season` column. Migrations must be backward-compatible with the previous
image (ADR 0003): expand, then contract.

CI enforces this with `uv run python -m fplbot.store.migration_check`: an `upgrade()` that drops
or renames a table or column (Alembic ops or raw SQL) fails unless the module says
`contract_step = True`. Write that contract migration only once no deployed image reads the old
shape.
