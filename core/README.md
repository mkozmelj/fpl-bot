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
    clock.py                     Clock protocol + SystemClock
    logs.py                      logging setup (no identifiers in logs)
    sources/                     FPL adapter: FplTransport (raw GET), FplSource (fail-soft),
                                 FakeFplTransport (recorded fixtures)
    store/                       schema.py, migrations/ (Alembic), members.py, seasons.py, db.py
    prediction/ optimisation/    Phase 2/3, empty
    advice/                      pure decisions (Gaps, Rivals, Price alert)
    explain/                     Phase 2, empty
    delivery/                    telegram.py (PTB wiring), conversation.py (text in, replies out),
                                 texts.py (all wording), rate_limit.py
    jobs/                        scheduled jobs (ticket 31)
  tests/
    harness.py                   THE test seam (see below)
    conftest.py                  throwaway database + `bot` fixture
    fixtures/fpl/                synthetic FPL API fixtures, mirroring API paths
```

Dependency direction: `delivery -> advice -> prediction/optimisation -> store -> sources`, with
`jobs` orchestrating all of them. Only `delivery` knows about chats.

## Running locally

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

Optional: `FPL_FIXTURES_DIR` points the fake source at another fixture directory. The live FPL
source arrives with ticket 27; until then `FPL_SOURCE=fake` is required.

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
| `FakeFplTransport` | the live FPL HTTP transport | `bot.fpl.respond(path, FplResponse(403))`, `bot.fpl.requested_paths` |

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

Extending the harness: button presses (callback queries) and scheduled-job ticks belong in
`BotHarness` (`deliver_text` shows the update shape; `advance` is where due jobs should run once
the scheduler exists). `FakeTelegram._result` answers Bot API methods; add a case when the bot
starts calling a new method whose result it reads.

## FPL fixtures

`tests/fixtures/fpl/` mirrors API paths: `bootstrap-static/` is served from
`bootstrap-static.json`, `entry/1001/event/11/picks/` from `entry/1001/event/11/picks.json`. A
path without a file answers 404. Script awkward answers per test with
`bot.fpl.respond("bootstrap-static/", FplResponse(503, b'"The game is being updated."'))`;
several responses are served in order and the last one repeats.

Fixtures are small and synthetic (made-up clubs and Footballers). Never commit real FPL data.

## Migrations

Add a revision under `src/fplbot/store/migrations/versions/` (hand-written or
`DATABASE_URL=... uv run alembic revision --autogenerate -m "..."`), update `store/schema.py`, and
give every new table a `season` column. Migrations must be backward-compatible with the previous
image (ADR 0003): expand, then contract.
