# 26: Walking skeleton: invite and redeem

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** the first end-to-end path through the bot, plus everything later tickets build on. The owner sends `/invite` and gets a single-use code and a `t.me/<bot>?start=<code>` link. A friend who opens the link is allow-listed at once and greeted. Anyone else gets silence. The bot runs locally with zero keys against a fake FPL source and a local Postgres.

Foundations this ticket lays (shape fixed by ticket 12 and ADRs 0001-0003):
- Monorepo layout: the Python package `fplbot` (src layout) under `core/`, with the subpackages `sources`, `store`, `prediction`, `optimisation`, `advice`, `explain`, `delivery`, `jobs` and the dependency direction from the spec. Python 3.14, `uv` with a hashed lockfile, `ruff`, `pyright`, `pytest`.
- SQLAlchemy 2.0 async (psycopg 3) with Alembic. Every table has a `season` column from the first migration.
- The **one test seam** from the spec: a harness that feeds Telegram updates and scheduled-job ticks into the running bot, with a fake clock, a fake Telegram client that records outgoing messages, recorded FPL fixtures behind the sources adapter, and a real throwaway Postgres. Tests assert only on what the fake Telegram client receives and on externally meaningful rows.
- A sources adapter interface with a fake FPL implementation that serves recorded fixtures. Later tickets add endpoints and politeness behind it.
- Config from environment: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, owner Telegram ID. Nothing else required.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Owner `/invite` replies with a single-use start link; the code has at least 64 bits of randomness, is stored only hashed, and expires after 48 hours (security ticket 16 overrides the prototype's 7 days).
- [ ] Opening the link (`/start <code>`) allow-lists the chat immediately, marks the invite used, and greets the friend (setup itself is ticket 28).
- [ ] The Member cap is 10: a valid code redeemed when 10 Members exist is refused with "Sorry, this bot is full".
- [ ] Unknown chats get no reply to anything, including `/start` with no code or a code that never existed. A `/start` with a real code that is used, expired or over the cap gets one short reply so an invited friend isn't left guessing.
- [ ] Wrong code attempts are rate-limited per chat.
- [ ] Group chats are ignored entirely; only private chats are served.
- [ ] Logs carry an internal Member number only, never chat IDs, team IDs or names.
- [ ] The bot starts locally with no secrets besides a bot token and DB URL (fake FPL source selectable), and the test suite runs with no secrets at all.
- [ ] Tests through the seam cover: invite redeem, cap reached, stranger silence, used and expired code.
