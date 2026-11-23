# Architecture, frameworks and hosting for v1

Type: grilling
Status: resolved
Assignee: owner
Blocked by: 01, 07, 08, 09

## Question

Given the research on the FPL API, solvers, Claude on hosting and free hosting, what is the v1 architecture? Decide:
- Python framework and libraries: web or API layer, scheduler, Telegram library, ORM, and solver.
- Database.
- Hosting and scheduling stack.
- How Claude is called: CLI on a subscription, or the API.
- Repo layout for the Python core plus the later TypeScript web app (monorepo?).
- Module boundaries: ingestion, prediction, optimisation, advice, delivery.

Record the hard-to-reverse choices as ADRs.

## Answer

Resolved by grilling with the owner, 2026-11-19.

- **Hosting:** the owner's existing **Railway Hobby** plan, one always-on service in EU West (Amsterdam). Data lives in **Neon** free Postgres (EU), not Railway Postgres. This adds roughly $2–5 a month, mostly RAM, inside Hobby's $5 included usage, which is shared with the owner's other project. Oracle Always Free and GCP e2-micro remain the fallback for the same container. See [ADR 0001](../../../docs/adr/0001-railway-and-neon-hosting.md).
- **Process model:** a modular monolith, as one container running one asyncio Python process with the Telegram bot, scheduler and jobs. CPU-heavy work (solver, xP fits) runs in short-lived subprocesses so the long-lived process stays small, which keeps RAM cost down and replies responsive.
- **Networking:** Telegram **long polling**, so there is no inbound HTTP in v1 and no webhook. FastAPI joins the same process in the web-dashboard phase.
- **Libraries:**
  - Python **3.14**
  - `uv` with a hashed lockfile
  - `ruff`, `pytest` and `pyright`
  - `pandas`
  - `python-telegram-bot` v22
  - **APScheduler 3.x** (`AsyncIOScheduler`), with no persisted job store: jobs are rebuilt from the DB and FPL deadlines at startup and after each data refresh, with a misfire grace window
  - **SQLAlchemy 2.0** (async, psycopg 3) with **Alembic** migrations, using Neon's pooled connection string and short idle timeouts so it scales to zero
- **Solver:** we **write our own** on `highspy`, porting open-fpl-solver's formulation with Apache-2.0 attribution. Upstream is used only as a CI regression oracle. See [ADR 0002](../../../docs/adr/0002-own-solver-on-highs.md).
- **Claude:** the API key (not the subscription), through the official `anthropic` SDK. The default model is **Sonnet 5.5** and is a config setting; Opus is an option later for research-style Scout work. Batch API for Member summaries, and a hard monthly spend limit in the Console. Claude sits behind one `explain` interface and is **optional**: with no key, the bot falls back to templated text, so forks and local dev run with zero keys. Estimated cost is about $5–10 a season.
- **Repo:** a monorepo, with the Python package `fplbot` (src layout) in `core/`, the TypeScript app later in `web/`, and `docs/adr/`, `GLOSSARY.md` and `deploy/` at the root.
- **Modules** (subpackages of `fplbot`), with dependencies flowing `delivery → advice → prediction/optimisation → store ← sources` and `jobs` orchestrating:
  - `sources`: fail-soft adapters
  - `store`
  - `prediction`
  - `optimisation`
  - `advice`: Gaps, captain, bench, transfers, Chips and Price alerts, all as pure decisions
  - `explain`
  - `delivery`: the only module that knows about chats
  - `jobs`
- **Pipeline (GitHub Actions, no manual steps):**
  - `main` is protected. Every change goes through a PR with required checks and auto-merge.
  - The checks are lint, types, unit tests, integration tests against a throwaway Postgres service container (no DB secrets in CI) and the solver regression test.
  - CI then builds one image, scans and signs *that* image, and pushes it to public GHCR.
  - It deploys with `railway redeploy` using a project token scoped to the production environment, then runs a smoke check with automatic rollback.
  - There is no standing staging environment. Playwright UI tests join when the dashboard does.
  - The Railway MCP is for development and observability only, never a deploy path.
- **Handed on:**
  - Which security tools fill the pipeline's gates goes to [Security and secret handling for a public open-source repo](16-security-and-open-source-hygiene.md).
  - FPL reachability from Railway's shared IPs, and solver timing, go to [Probe Railway: FPL reachability and solver timing](18-probe-railway.md).
