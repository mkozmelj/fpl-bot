# Map: FPL Bot

Label: wayfinder:map

## Destination

A set of build-ready, phased specs and tickets for an open-source FPL advisory bot, ready to hand to `/to-spec` or `/implement-spec`. The bot serves 5–10 invited Members through Telegram first (a TypeScript web dashboard comes later). It predicts Expected points, sends a nightly Price alert, shows Elite and Rival gaps, and recommends transfers, captain, bench and Chips. It runs at zero spend apart from minimal Claude usage.

Phases:
1. A Member's own Squad, Rivals and Elite gap, plus the nightly Price alert.
2. Expected points, captain and bench advice.
3. A transfer planner and chip planner.
4. Autopilot as a paper simulation: the bot runs its own simulated Squad under real rules, scored from public data, starting around GW20.

## Notes

- **Vocabulary:** use [GLOSSARY.md](../../GLOSSARY.md) terms everywhere: Member, Squad, Footballer, Rival, Mini-league, Followed league, Elite cohort, Gap, Price alert, Watch list, Goal, Analyst mode, Scout overrides, Autopilot, Ghost Squad.
- **Skills:** research tickets use `research`. Grilling tickets use `grilling` plus `domain-modeling`. Prototype tickets use `prototype`. Record ADRs in `docs/adr/` when a choice is hard to reverse.
- **Stack preferences:** Python for the API, data, prediction and optimisation. TypeScript for the web UI. Telegram first, and a web dashboard in a later phase. The v1 architecture is fixed in [Architecture, frameworks and hosting for v1](issues/12-architecture-and-framework.md) and [ADRs](../../docs/adr/). Deploys happen only through the GitHub Actions pipeline, never by hand.
- **Money:** no new paid services beyond the owner's existing Railway Hobby plan (about $2–5 a month extra, inside its included usage) and prepaid Anthropic API credit for Sonnet 5.5 (about $5–10 a season, with a hard spend limit). Otherwise free tiers only. Claude usage is minimised: plain code does the maths, and Claude only explains, plus the Scout overrides leftover parse.
- **Scout overrides:** scripts collect and pre-filter news first, and Claude sees only the condensed leftovers, once per Gameweek, shared across all Members. It is a pipeline step, not a Member-facing mode.
- **Advice only for real Members:** the bot never holds a Member's FPL password. Autopilot is a paper simulation only: no FPL account, no login, no writes.
- **Goal:** Overall rank is the default. Mini-league is secondary, and a Member can switch to it mid-season when they're out of overall contention.
- **Price alert:** defaults to 20:00 in the Member's local time, configurable per Member, and silent when there's nothing to report.
- **Elite ownership:** first look for published top-1k/10k/100k data. Fall back to our own sampled scraping, kept within rate limits.
- **No Member telemetry:** no tracking of whether Members followed advice, and no in-bot feedback collection. Friends give feedback informally or through GitHub issues. The bot may measure the accuracy of its *own* predictions.
- **Public, open-source repo:** no secret ever goes in the repo. Treat security as a first-class requirement.
- **Requests to outside services** never carry the owner's or a Member's personal details (in headers, user agents or URLs).

## Decisions so far

<!-- one line per closed ticket: [title](issues/NN-slug.md): gist -->

- [FPL official API: what's in it and what it allows](issues/01-fpl-official-api.md):
  - **No login needed:** Advice mode runs entirely on public endpoints (bootstrap-static, fixtures, live, any Manager's entry/history/transfers/picks, classic and H2H standings).
  - **Picks after the deadline only:** Rival and Elite gaps work on locked Squads.
  - **Not public:** free transfers and selling prices, which have to be derived.
  - **FPL's own price predictor is public** (`price_change_projections` and friends), which Price alerts can use.
  - **Terms:** they ban automated extraction, commercial use and multiple accounts, so the bot stays non-commercial and low-load. This rules out a Sandbox account.
  - **Rate limits:** none published; the CDN caches responses, so about 1 request per second is polite.

- [Can Claude run on a host using a subscription, and what does the API cost otherwise?](issues/08-claude-cli-on-hosting.md): A headless subscription token (`claude setup-token`) works and is fine for the owner's own jobs. Serving Members through it is close to Anthropic's explicit bans, so the hosted bot should use an API key on Haiku 5.5, about $0.50–1.10 a season, or free on a Max plan's included API credits. The owner is on **Pro**, so the hosted bot uses an API key (a few dollars of prepaid credit covers the season), and the subscription is only for development.
- [Free hosting, database and scheduling options](issues/09-free-hosting-and-scheduling.md): The recommendation is one Python process on an Oracle Always Free VM (in-process scheduler plus Telegram long polling), Neon free Postgres, and Cloudflare Pages for the dashboard, with a GCP e2-micro as backup. GitHub Actions cron is too unreliable and its terms rule it out as the scheduler. Watch for Oracle reclaiming idle VMs and for FPL blocking cloud IPs. *Superseded for the primary host by the architecture ticket (Railway); Oracle and GCP remain the fallback.*
- [2026/27 chip rules and how to time each chip](issues/06-chip-rules-and-strategy.md): 8 Chips in two sets (Wildcard, Free Hit, Bench Boost and Triple Captain for GW1–19 and for GW20–38), one per Gameweek. The first set expires at the GW19 deadline, 1 Jan 2027 18:30 UTC. Read the windows from the API (`chips[]`, `events[].deadline_time`). No blank or double Gameweeks exist yet: BGW30 and BGW33 are projected with high confidence, DGW32/35/36 with medium. The planner should solve Chips jointly with transfers as a multi-period MIP (mixed-integer program), with FPL-Optimization-Tools as the reference.
- [Can a bot make transfers on an FPL account, and is it allowed?](issues/11-fpl-automation-feasibility.md): It works technically: PingOne OIDC bearer token, then `POST /api/transfers/` and `/api/my-team/{entry}/`. But login is fragile, and AIrsenal's broke three times in 2025/26. The terms ban automation (28(d)) and more than one account per person (clause 6), and a ban can reach the person's real team (36–37). The recommendation is Autopilot as a **paper simulation** on public data, with no live account. **Owner chose the paper simulation** (2026-11-19).
- [How the best FPL managers make decisions in 2026](issues/05-elite-manager-methods.md):
  - **Core method:** maximise multi-Gameweek xP over a 6–8 GW horizon with decay 0.85–0.9. Port the defaults from FPL Review and Sertalp's Apache-2.0 solver.
  - **Hits and transfers:** hits are rare. Take a -4 only if the decayed gain beats 4, plus the value of the rolled free transfer given up, plus a noise margin.
  - **Squad shape:** team value and bench barely matter.
  - **Captaincy:** pick the highest-xP captain, using EO only to break ties.
  - **Goal:** it changes only the reference group (Elite or Rival EO) and the risk, via z = lead / (σ√GWs left): shield when ahead, add variance when behind.
  - **Judging advice:** score it on xP, not on realised points.
- [Where to get top-1k / 10k / 100k ownership data](issues/03-elite-ownership-sources.md): No free source publishes Elite ownership with reuse permission. LiveFPL has the data, but its JSON is unlicensed, so use it only as a cross-check or ask its author. FFHub and FFFix ban reuse, and FPL Review's Elite 1000 is a fixed list. So we build our own sampler on the official API, as a post-deadline job: all 1k, about 1,940 from the top 10k and about 2,350 from the top 100k (±2%), roughly 4,400 requests and 25 minutes at 3 req/s per Gameweek, with cut-offs by `rank_sort`.
- [Open-source expected-points models and transfer solvers to reuse](issues/07-xp-models-and-solvers.md): Combine. Build our own lightweight component xP model, borrowing AIrsenal's structure (team goals, share of goals, minutes, point components) and backtest metrics. No open model fits 2026/27 as-is. Vendor `solioanalytics/open-fpl-solver` (Apache-2.0, formerly Sertalp's) on `highspy` 1.16. It covers transfers, rolling FTs, hits, XI/captain/bench and all chips, and rebuilds bank and free transfers from public data. We add Mini-league Goal terms. The baseline to beat is FPL's `ep_next`. Minutes is the main accuracy lever. Solve time on Oracle A1 is still to be measured.
- [Free, legal football stats sources for predictions](issues/02-free-stats-sources.md): The FPL API already carries xG, xA, xGI, xGC, defensive contribution/CBIT, starts and set-piece order per Footballer and Gameweek, so it is the core source. Add the football-data.co.uk odds and match-xG CSV, fetched at runtime and never committed, plus The Odds API's free plan as an opt-in adapter that needs a key. vaastav is for backtests only. Avoid FBref (Opta data removed Jan 2026, scraping forbidden), Understat (no terms, blocks scripts), the ClubElo API (deactivated), FotMob, Sofascore and scraping premierleague.com. Put each source behind a fail-soft adapter.
- [How FPL price changes work and how to predict them](issues/04-price-change-mechanics.md):
  - **Official predictor:** FPL publishes its own Price change predictor in `bootstrap-static` (`price_change_percent`, hourly rate, likelihood −5..+5 for the next 3 deadlines), refreshed every 15 minutes. Changes happen at 00:00 UK, at most £0.1m a day.
  - **Alerts:** build Price alerts on these official fields. Don't reuse third-party predictors (no licence). A home-grown model is needed only as a fallback.
  - **History:** archive `/api/stats/price-changes/` daily for accuracy ground truth.
  - **Evening surge:** the official linear projection under-predicts it, so re-check late in the evening.
- [Legal free team-news sources for Scout mode](issues/10-news-sources-for-scout.md): The only legal, automatable source is the FPL API's own news fields (`news`, `status`, `chance_of_playing_*`, and the new `scout_risks` and `scout_news_link`). BBC, Guardian, PL site, club sites, line-up sites and Reddit all ban automated or AI use. The FPL text is templated, so regex handles nearly everything, and Claude sees only the unparsed changes plus notes Members paste in: about 0–3k tokens per Gameweek.

- [Architecture, frameworks and hosting for v1](issues/12-architecture-and-framework.md):
  - **Hosting and data:** the owner's Railway Hobby plan (EU, one always-on container), with data on Neon Postgres.
  - **Runtime:** a modular monolith on Python 3.14, using python-telegram-bot with long polling, APScheduler, and SQLAlchemy with Alembic.
  - **Solver:** our own, on HiGHS, derived from open-fpl-solver.
  - **Claude:** Sonnet 5.5 through the API, and optional.
  - **Repo:** a monorepo in which `fplbot` is split into sources, store, prediction, optimisation, advice, explain, delivery and jobs.
  - **Delivery:** a PR-gated GitHub Actions pipeline that builds, scans and signs one image, then deploys it with a scoped Railway token, smoke-checks it and rolls back on failure.

- [Telegram flow for joining and the Phase-1 commands](issues/14-telegram-onboarding-flow.md): Approved as prototyped ([simulator](prototypes/14-telegram-flow-PROTOTYPE.html)). Owner-only `/invite` makes single-use codes (cap 10 Members) that allow-list the chat on redeem; the Member links a team ID and confirms the team name (a team already linked is refused); Goal by buttons, with Overall rank as the fallback when there is no private league; timezone by buttons or typed city, with the Price alert at 20:00 local, changed by `/time`; any command abandons a question and stale buttons are ignored; `/leave` deletes the Member's data.

- [Security and secret handling for a public open-source repo](issues/16-security-and-open-source-hygiene.md):
  - **Licence:** Apache-2.0 with a `NOTICE`.
  - **Secrets:** runtime secrets only in Railway sealed variables. The Railway project token is the only CI secret, in a `main`-restricted GitHub Environment.
  - **Gates:** gitleaks (hook and CI), CodeQL, `pip-audit`, Trivy, cosign signing with provenance, SHA-pinned Actions with actionlint and zizmor. Dependabot PRs are merged by hand.
  - **Members:** `/leave` hard-deletes, there are no identifiers in logs or prompts, and unknown chats get silence.
  - **Scout notes:** Claude has no tools, and its output must parse against a strict schema.
  - **Docs:** `SECURITY.md`, `PRIVACY.md`, `.env.example` and a secrets runbook.

- [Which data the bot collects, how often, and what it keeps](issues/13-data-ingestion-design.md):
  - **Sources:** the FPL API only in Phase 1, plus football-data.co.uk from Phase 2.
  - **Politeness:** one shared limit of at most 1 req/s with a generic User-Agent; a 403 is never retried.
  - **Fetching:** `bootstrap-static` when needed (about 25–30 a day), held in memory.
  - **Price data:** 5 snapshots a night in the DB, plus the daily `/stats/price-changes/` archive.
  - **Post-deadline jobs:** Elite cohorts fixed before kickoff, then Member and Rival picks, then our own ±2% Elite sampler (about 73 minutes).
  - **Rivals:** come from Followed leagues.
  - **Storage:** aggregates only, never raw JSON or sampled managers.
  - **Reliability:** jobs are idempotent with startup catch-up.

- [What the nightly Price alert says and when it fires](issues/15-price-alert-spec.md):
  - **Content:** Likely (±4) or more only. Owned Footballers for falls, Watch-list Footballers for rises, plus a "tomorrow night" line for ±5 only. It states the £0.1m saving and gives no transfer advice.
  - **Delivery:** one plain-text message a night, with no Claude call, at the Member's time clamped to 17:00–23:15 UK. It carries a stale-Squad caveat before deadlines and is silent on quiet nights or data failures, where the owner is told instead.
  - **Accuracy:** hit rate per likelihood code, read through an owner-only `/accuracy`. Floors are 70% for ±4 and 85% for ±5 over 14 nights, and any threshold change is manual.

- [Autopilot paper simulation: rules and how it's shown](issues/17-autopilot-paper-simulation.md):
  - **Start:** the first Gameweek at or after GW20 when the solver is ready, with a free £100m solver build and the full second chip set.
  - **Locking and scoring:** decisions lock after the deadline −90 min fetch and are visible after the deadline. Scoring follows the full rules from public data, and the scorer's acceptance test is replaying a real Member's season exactly.
  - **Six Ghost Squads by Tactic:** Core, Template, Differential, Active, Patient, and a Baseline on FPL's `ep_next`. Settings are frozen at the start. The cap is 6, and Active drops first if solve times don't fit.
  - **Shown as:** a Core row in league tables, an on-demand `/ghost` leaderboard and an estimated rank band, with no unsolicited messages. Judged on both points and xP, and no winner before GW38.

- [Elite gap, Rival gap and the mini-league progress view](issues/19-gap-views.md):
  - **Edge:** (you start − reference XI share + you captain − reference captain share) × weight, in points per Gameweek. The weight is recent form in Phase 1 and xP in Phase 2.
  - **Display:** top 3 each side, hidden under 2× margin of error or 0.35 pts, no net total, freshness always labelled.
  - **Rivals:** the nearest 2 above and below by rank in the Goal league, or `all`; head-to-head is one Rival.
  - **Timing:** between deadlines it uses the last-deadline Squad with a caveat.
  - **League view:** movement arrows and gaps above and below, with the Ghost Squad as one row later.

- [Expected-points model design](issues/20-xp-model-design.md):
  - **Shape:** a component model (team goals, share of goals, minutes, point components) with Poisson and shrunk rates, no ML framework. FPL's `ep_next` plus a last-5 average stay as the Baseline.
  - **Minutes:** start probability × minutes if started, and the only place Scout overrides plug in.
  - **Horizon:** 5 Gameweeks stored, decay 0.85, with 3 and 8 as backtested settings.
  - **Bar to ship:** beat `ep_next` on MAE and rank correlation out of sample on 2024/25 and 2025/26.
  - **Form:** a pure function in the `prediction` module.

- [Captain and bench logic](issues/21-captain-and-bench-logic.md):
  - **Captain:** highest next-Gameweek xP, tie band 0.3 xP, ties broken by the higher Elite captain share (no λ term). Top 3 shown.
  - **Vice-captain:** best xP from a different match, start probability about 85% or more.
  - **XI and bench:** XI by xP; bench by P(needed) × xP-if-plays, computed in plain code, with the backup goalkeeper fixed.
  - **Mini-league Goal:** changes the captain only, via z = L / (σ√n) with empirical σ shrunk to a prior of about 15. When Behind (n ≤ 6) it offers a differential within 10% of top xP.
  - **Delivery:** on demand against the last-deadline Squad, in a fixed template with no Claude call and no push. Chips are left to the chip planner.

- [Probe Railway: FPL reachability and solver timing](issues/18-probe-railway.md):
  - **Reachability passes:** 1,359 of 1,359 public FPL requests returned 200 from Railway EU West's shared IP over 45 h, including the GW11 deadline, with no 403s or 429s. Standings mostly miss the CDN, so sample them sparingly.
  - **Solver:** upstream on `highspy` solves 8 GW without chips in ≤ 18 s and 0.4 GB on 1 vCPU. Budget: gap 0.5%, `time_limit` 60 s, HiGHS `threads` = vCPUs, because HiGHS sees 48 host cores otherwise. Joint all-chip solves fit only up to 4 GW. The probe project was deleted.

- [Analyst-mode summaries and the fate of Scout mode](issues/22-analyst-and-scout-modes.md):
  - **Claude surface:** only an on-demand `/why` (5 a day per Member) that adds prose around templated advice. There is no brief and no push, and alerts, captain and bench stay Claude-free.
  - **Scout:** folded into Analyst mode as a shared Gameweek job (regex first, Claude only on leftovers). It is renamed "Scout overrides".
  - **Notes:** `/note` is per Member, expires at the next deadline and never enters the shared job.
  - **Guardrails:** templated fallback on any failure, a numbers guard on Claude's prose, no tools or identifiers, and a hard spend limit.
  - **Check:** a forward shadow run. Regex overrides are live from day one, and Claude-derived ones stay off until they beat the baseline on minutes MAE over 8 Gameweeks.

- [Operations: monitoring, alerts, migrations and season rollover](issues/23-operations.md):
  - **Liveness:** the bot pings an optional `HEARTBEAT_URL` every 5 minutes while healthy. The owner's shared monitoring service watches it.
  - **Alerts:** one deduplicated Telegram DM to the owner with a "recovered" message.
  - **Migrations:** Alembic runs in Railway's pre-deploy command, so the DB secret never reaches CI (fallback: startup under an advisory lock). They stay backward-compatible, and the deploy is smoke-checked by a `ready sha=` log line.
  - **Backups:** a nightly `age`-encrypted export of the Member tables to the owner's Telegram chat. The rest relies on Neon's restore window.
  - **Rollover:** owner-confirmed `/rollover`, with a `season` column on every table.
  - **Owner tools:** a read-only `/status` and cost guards.
- [Spec: Phase 1, Squad, Rival and Elite gaps, and the nightly Price alert](issues/25-spec-phase-1.md): Implemented in tickets 26-42 on branch `spec-25-phase-1` (171 tests green). Deferred from the code review: splitting `member_flow.py` and `sources/fpl.py`, keying the Watch list on the Member number instead of the chat ID, and de-duplicating the workflows' tool-install steps. To check before go-live: whether FPL issues new team IDs each season (rollover keeps them), and that Railway's pre-deploy migration runs on the image service.

## Not yet specified

- **Transfer planner:** rolling free transfers, when to take a hit, team-value considerations, and how Elite and Rival gaps feed into it. The horizon is settled by solve time: the xP model's 5 Gameweeks by default, up to 8 allowed, taking ≤ 18 s and 0.4 GB on 1 vCPU with HiGHS `threads` capped to the vCPUs (see [Probe Railway: FPL reachability and solver timing](issues/18-probe-railway.md)).
- **Chip planner:** choosing the Gameweek for each 2026/27 Chip (including any second-half set), and re-planning as double and blank Gameweeks are announced. Follows the xP model. The probe rules out freeing all Chips in one 8-GW MIP (it runs out of memory at 2 GB); joint solves fit up to 4 GW (about 48 s), so longer chip timing means enumerating forced-chip scenarios.
- **Prediction self-evaluation:** backtesting xP against outcomes (the Baseline-versus-Core Ghost Squads in [Autopilot paper simulation: rules and how it's shown](issues/17-autopilot-paper-simulation.md) are the end-to-end check), kept separate from any Member tracking. The backtest method is set in [Expected-points model design](issues/20-xp-model-design.md). Price-prediction accuracy is already set in [What the nightly Price alert says and when it fires](issues/15-price-alert-spec.md). The Scout-overrides shadow comparison is set in [Analyst-mode summaries and the fate of Scout mode](issues/22-analyst-and-scout-modes.md).

## Open tickets

- [Web dashboard: views and auth](issues/24-web-dashboard.md): grilling, on the frontier.

## Out of scope

- **Building the bot.** This map ends at specs; implementation is a separate effort with `/implement-spec`.
- **Autopilot on any real FPL account** (a Member's, a Sandbox or second account, or a consenting friend's): breaks FPL terms clauses 6 and 28(d), and a ban can reach the owner's real team. The owner chose a paper simulation instead. See [Can a bot make transfers on an FPL account, and is it allowed?](issues/11-fpl-automation-feasibility.md)
- **In-bot feedback or usage tracking of Members:** the owner doesn't want to see Members' behaviour.
- **Paid data sources or paid hosting:** zero-spend constraint.
- **A public, open-signup product:** invite-only, 5–10 Members. Forks can run their own instance.
