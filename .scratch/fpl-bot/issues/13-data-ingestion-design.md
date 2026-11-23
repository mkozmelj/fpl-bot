# Which data the bot collects, how often, and what it keeps

Type: grilling
Status: resolved
Assignee: owner
Blocked by: 01, 02, 03

## Question

Which sources does v1 ingest? On what schedule (relative to Gameweek deadlines and the nightly price update)? What does it store, and for how long (for example price-snapshot history kept for predictor training)? How do we stay polite to every source: caching, backoff, and a single user agent with no personal details?

Does Elite ownership come from an external publisher or from our own sampler?

## Answer

Resolved by grilling with the owner, 2026-11-19. It assumes FPL is reachable from Railway. The probe in [Probe Railway: FPL reachability and solver timing](18-probe-railway.md) passes so far, but its verdict is still provisional.

**Facts the design rests on**
- **Neon free tier:** 1 GB of storage and 100 compute-hours a month per project. It sleeps after 5 minutes idle, and every write wakes it, so storage and wake-ups are the binding limits, not FPL.
- **Hidden picks:** FPL keeps picks for an upcoming Gameweek hidden, even a Member's own. Between deadlines the bot only knows a Member's Squad as of the last deadline, plus their Watch list. A Price alert can therefore name a Footballer the Member has already sold this week.
- **"Updating" window:** FPL often answers "game is being updated" (503) for 20–60 minutes after a deadline.
- **Live ranks:** in 2026/27, overall ranks move live once matches start.

**Sources**
- **Phase 1:** the FPL API only.
- **From Phase 2:** the football-data.co.uk season CSV as well, fetched daily at 06:00 UK.
- **The Odds API:** an opt-in adapter, off by default, built only if the xP model needs it.
- **LiveFPL:** never in production; a manual cross-check during development only.
- **vaastav:** offline backtests only.

**Politeness**
- **Rate:** one shared limit for all FPL traffic, at most 1 request a second. Interactive commands and the Price alert go first; the Elite sampler yields to them.
- **User-Agent:** one generic, browser-style string, the same one the Railway probe tested. It carries no personal details, URL or repo name.
- **Conditional requests:** used wherever FPL returns an ETag or Last-Modified header.
- **429 and 5xx errors:** exponential backoff with jitter, honouring Retry-After, at most 5 tries.
- **403 errors:** never retried. The job pauses until its next scheduled run, and the owner gets a direct message.
- **football-data.co.uk:** the same rules apply.

**Schedule** (UK time)
- **`bootstrap-static`: fetched when needed, not on a fixed clock.** About 25–30 requests a day, with the latest copy kept in memory.
  - The 5 price-archive times: 18:00, 20:00, 22:00, 23:00 and 23:45.
  - 00:05, just after the nightly price run, together with an archive of `/stats/price-changes/` at 00:10.
  - Each distinct Price-alert time. Members who share a time share one fetch.
  - Hourly from 08:00 to 23:00 for news changes.
  - Deadline −90 min and −30 min, plus right after the deadline.
  - On demand when a command finds the in-memory copy more than 15 minutes old.
- **After each deadline:**
  - **Start:** at deadline +5 min, with one cheap probe call. While FPL is "updating", the job waits 10 minutes and probes again; these waits don't count as backoff tries.
  - **Order:** first the 450 standings pages that fix the Elite cohorts (about 8 minutes, to finish before the first kickoff), then Member and Rival picks, then the Elite picks sample, which may run past kickoff.
  - **Late read:** if the standings read only finishes after the first kickoff, the cohort is still used and the run is marked "read late".
- **Once the Gameweek is final** (`finished` and `data_checked`, about 09:00 the day after the last match): fetch `event/{gw}/live` once, then refresh each Member's history and each Followed league's standings. The same data scores the Ghost Squad.
- **No live polling during matches** in v1.

**Elite ownership**
- **Source:** our own stratified sampler on the official API, not an outside publisher.
- **Cohorts and precision:** the top 10k and the top 100k (no top-1k census), at ±2% with 95% confidence. That's about 4,400 requests per Gameweek, or about 73 minutes at 1 req/s. This replaces the 3 req/s assumed in [Where to get top-1k / 10k / 100k ownership data](03-elite-ownership-sources.md).
- **Output per Gameweek and cohort, per Footballer:** ownership (all 15 players), XI share, captain share and EO, plus chip usage, sample size and margin of error.
- **Partial runs:** a partial sample is published if each cohort reached at least half its target, with the margin of error recomputed (about ±2.8% at half). Otherwise the previous Gameweek's figures stay, labelled with their Gameweek. The two are never mixed.

**Rivals and Followed leagues**
- **Leagues followed:** every Mini-league of each Member with at most 50 managers, de-duplicated across Members, plus the Member's head-to-head opponent each Gameweek.
- **A Goal league bigger than 50:** we follow only its top 10 plus the 20 managers ranked directly above and the 20 directly below the Member.
- **Fetching:** picks are fetched once, after the deadline.
- **Joining flow:** unchanged from [Telegram flow for joining and the Phase-1 commands](14-telegram-onboarding-flow.md).

**What we keep**
- **Never stored:** raw FPL responses. The latest `bootstrap-static` lives in memory and is rebuilt at startup.
- **Kept across seasons** (small, and needed for backtests and self-evaluation):
  - Footballers, clubs, fixtures and Gameweeks
  - each Footballer's per-Gameweek stats, from `event/{gw}/live`
  - a log of news and status *changes*, written only when something changed
  - Price changes, from the daily `/stats/price-changes/` archive
  - Elite ownership results
  - **price snapshots:** 5 a night at the archive times; a compact row per Footballer with price, percent, hourly rate, the 3 likelihoods and lock flags. That's about 50 KB each, or about 70 MB a season.
- **Elite managers:** the sampled managers' IDs and picks are discarded once the job finishes. Only the aggregates are kept.
- **Rival picks:** kept for the season, and deleted when no Member follows that league anymore.
- **Member and Rival history:** cleared at season rollover. `/leave` still hard-deletes at once.
- **The repo:** no FPL or third-party data is ever committed.

**Reliability**
- **Re-runs are safe:** every ingestion job is idempotent and writes one completion row per Gameweek (`elite`, `picks`, `gw_final`, plus one `price_archive` per night).
- **Startup catch-up:** at startup the bot runs anything missing for the current and previous Gameweek. Locked picks never change, so a late catch-up is correct, apart from the "read late" cohort risk.
- **Not caught up:** missed evening price snapshots are skipped, never back-filled.
- **Owner alerts:** the owner gets a direct message on a 403 or on a second failure in a row. Wider monitoring belongs to the Operations fog.

**Launch backfill** (going live at GW11 or later)
- **Stats:** `event/{gw}/live` for every finished Gameweek, about 10 requests.
- **Members:** history and past picks, fetched when each Member joins.
- **Not backfilled:** past Elite ownership, because the standings have moved since. Price history covers only the endpoint's rolling 6 weeks of actual changes.

**Glossary:** added **Mini-league** and **Followed league**, and redefined **Rival** as a Manager in one of the Member's Followed leagues, or their head-to-head opponent.

**No ADR:** each choice here can be changed later without much cost.
