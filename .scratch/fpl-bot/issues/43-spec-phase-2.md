# Spec: Phase 2, Expected points, captain and bench advice, Scout overrides and `/why`

Type: spec
Status: open
Labels: ready-for-agent
Assignee: —
Blocked by: —

Source: [map](../map.md), with every decision taken from the resolved tickets 02, 05, 07, 10, 13, 16, 19, 20, 21 and 22, the [Phase 1 spec](25-spec-phase-1.md) it builds on, and ADRs 0001-0004. Vocabulary follows [GLOSSARY.md](../../../GLOSSARY.md). Decisions this spec had to take that no ticket settled are marked **(new)**; the owner accepted all of them on 2026-11-26. Tickets 44-59 implement it.

## Problem Statement

Phase 1 shows Members where their Squad differs from their Rivals and the Elite cohort, but says nothing about what to do next. The Gap is weighted by recent points, which lag behind fixtures, injuries and rotation. Members still choose their captain, vice-captain and bench order by hand. FPL's own `ep_next` is a weak, unexplained guide. Team news sits in FPL's news fields, and nobody turns it into a change in expected minutes. When the bot does give advice, Members have no way to ask why.

## Solution

The bot gains its own Expected points (xP) model and uses it for on-demand advice, still in Advice mode on public data, with no FPL login:

- An xP model built from parts produces xP and expected minutes (xMins) per Footballer for the next 5 Gameweeks. It must beat FPL's `ep_next` in a backtest before Members see it.
- `/captain` recommends the captain (top 3 with xP), the vice-captain and the reason. When a Member's Goal is Mini-league, the captain pick adjusts to the Member's standing against their Rivals.
- `/bench` recommends the starting XI and bench order, with P(needed) for each sub and a warning when a likely-blank starter can't be covered by a legal autosub.
- The Elite gap and Rival gap switch their weight from recent points to next-Gameweek xP. The formula stays the same.
- Scout overrides: a shared job parses FPL's news fields with regex and adjusts start probability and minutes. Claude sees only the lines the regex can't parse. Claude-derived overrides stay off until a shadow comparison shows they help.
- `/note`: a Member can paste team news that affects only their own advice. It expires at the next deadline.
- `/why`: Claude adds a short "because…" paragraph around the templated advice, capped at 5 a day per Member. The plain template is the fallback whenever Claude is unavailable or its text fails the numbers guard.
- The owner's `/accuracy` gains xP-versus-realised and Scout-shadow reports.

This is the first phase with a Claude call. Claude is always optional: with no API key, the bot behaves exactly the same apart from `/why` prose and the Claude-parsed leftovers.

## User Stories

Expected points

1. As the owner, I want the bot to compute xP and xMins for every Footballer for the next 5 Gameweeks, so that captain, bench and Gap advice share one prediction.
2. As the owner, I want double Gameweeks to sum per-fixture xP and blank Gameweeks to give 0, so that the fixture list is handled correctly.
3. As the owner, I want xP recomputed after each Gameweek is final, each morning after the odds data arrives, and at deadline −90 minutes with the latest news, so that advice is fresh where it matters.
4. As the owner, I want a backtest command that scores the model against `ep_next` and a last-5 average on 2024/25 and 2025/26, so that I know whether it is worth shipping.
5. As the owner, I want the model's advice switched on for Members only once it beats `ep_next` on MAE and rank correlation in both seasons, so that Members never get advice worse than FPL's own number.
6. As a Member, I want advice before that bar is passed to come from the Baseline and say so, so that I know what the advice rests on.
7. As the owner, I want every model setting (horizon, decay, tie band, start-probability floor, σ prior, differential allowance) in one settings module, tuned by the backtest, so that I can change it without touching the logic.

Captain and vice-captain

8. As a Member, I want `/captain` to show the top 3 captain options with their xP, so that I can see how close the choice is.
9. As a Member, I want options within 0.3 xP of the top called "too close to call", with the tie-break named, so that I'm not given false precision.
10. As a Member whose Goal is Overall rank, I want ties broken by the Elite captain share of the cohort that matches my rank, so that close calls follow good practice.
11. As a Member, when Elite figures are missing or stale, I want the higher xP to win and the message to say so, so that the advice is honest about its data.
12. As a Member, I want a vice-captain from a different match with a start probability of about 85% or more, so that a late benching of my captain doesn't leave me with a weak backup.
13. As a Member whose Goal is Mini-league and who is ahead of my Rivals, I want the captain to match my Rivals' most common captain when it is in the tie band, so that I protect my lead.
14. As a Member who is behind with 6 or fewer Gameweeks left, I want a captain my leading Rival doesn't have offered when it is within 10% of the top xP, labelled a variance choice, so that I can catch up.
15. As a Member who is too far behind to catch up, I want to be told honestly and pointed to switching my Goal back to Overall rank, so that I don't chase a lost cause.
16. As a Member, I want each reason tagged Evidence (xP), Practice (Elite or Rival share) or Goal risk, so that I see what drives the pick.

XI and bench

17. As a Member, I want `/bench` to show the starting XI that maximises xP within a legal formation, so that I don't miss points on my bench.
18. As a Member, I want outfield subs ordered by P(needed) × xP-if-plays, with P(needed) shown, so that the most useful sub comes on first.
19. As a Member, I want the backup goalkeeper always shown as the sub goalkeeper, so that the order is legal.
20. As a Member, I want a warning when a likely-blank starter can't be covered by a legal autosub, so that I fix it before the deadline.

Shared rules for advice

21. As a Member, I want captain and bench advice based on my last-deadline Squad, with a caveat saying so, so that I can adjust for transfers I've made since.
22. As a Member who played a Free Hit at the last deadline, I want advice based on the Squad my team reverts to, so that I'm not advised on a Squad I no longer have.
23. As a Member, I want captain and bench advice only when I ask, so that the Price alert stays the only unsolicited message.
24. As a Member, I want the advice to assume no Chip is active, so that it's clear what it covers.

Gap with xP

25. As a Member, I want the Elite gap and Rival gap weighted by next-Gameweek xP instead of recent points, so that the difference reflects what's coming.
26. As a Member, I want the Gap header to say the weight is xP, so that I can compare it with what I saw before.

Scout overrides and notes

27. As the owner, I want FPL news text parsed by regex into start-probability and minutes overrides every time xP is computed, so that injuries and suspensions reach the advice at no cost.
28. As the owner, I want the news lines the regex can't parse sent to Claude once a Gameweek, shared across all Members, so that Claude spend stays tiny.
29. As the owner, I want Claude's output parsed against a strict schema (Footballer ID, minutes change, confidence) and rejected otherwise, so that a bad reply can't corrupt predictions.
30. As the owner, I want Claude-derived overrides logged but off until they beat the no-override baseline on minutes MAE over at least 8 Gameweeks, so that only proven inputs change advice.
31. As a Member, I want `/note <text>` to record team news I've seen, at most 500 characters and 3 per Gameweek, so that my own advice can use it.
32. As a Member, I want my notes to affect only my own advice and expire at the next deadline, so that one Member's guess never changes anyone else's advice.
33. As a Member, I want to be told whether my note is currently changing my advice or only being tested, so that I'm not misled.
34. As a Member, I want `/leave` to delete my notes too, so that my data really is gone.

`/why`

35. As a Member, I want `/why captain`, `/why bench` and `/why gap` to explain the matching advice in a short paragraph, so that I understand the reasoning.
36. As a Member, I want `/why` limited to 5 a day, with the plain template once I'm over the limit, so that costs stay bounded without blocking me.
37. As a Member, I want `/why` to fall back to the plain templated reasons when Claude is unavailable, slow, over budget or fails the numbers guard, so that I always get an answer.
38. As a Member, I never want to be told about spend or limits on the owner's account, so that the bot stays simple.
39. As the owner, I want Claude's prose rejected if it names a Footballer or number not in the structured input, or runs over about 120 words, so that it can't invent facts.
40. As the owner, I want no tools, no network access and no Member identifiers in any prompt, so that a prompt can't leak data or act.
41. As the owner, I want a hard monthly spend limit in the Anthropic Console plus the in-app daily cap, so that spend can never run away.

Owner and checking

42. As the owner, I want `/accuracy xp` to show each finished Gameweek's xP MAE and rank correlation against `ep_next` and the last-5 average, so that I see live accuracy.
43. As the owner, I want a captain report per Gameweek: the bot's pick, the top-xP pick, FPL's most-captained Footballer and `ep_next`'s pick, with realised points, so that I can judge captaincy without tracking Members.
44. As the owner, I want `/accuracy scout` to compare xMins and xP with and without overrides, split by regex and Claude, so that I know whether the overrides help.
45. As the owner, I want `/status` to show the last xP run, the model in use (Core or Baseline), whether Claude is configured, and today's `/why` and Scout call counts, so that I can see Phase 2's health at a glance.
46. As the owner, I want a DM when the xP job fails or the odds source is down for 2 days in a row, so that I notice quietly degraded advice.
47. As a contributor, I want the model, captain and bench logic to be pure functions that run with zero keys and recorded fixtures, so that I can develop and test without secrets.

## Implementation Decisions

Architecture (unchanged from Phase 1, ADRs 0001-0004)

- Same single asyncio process on Railway and Neon Postgres, same custom scheduler and the same dependency direction: delivery → advice → prediction → store → sources, with jobs orchestrating. `optimisation` stays empty in Phase 2: the XI is chosen by enumerating legal formations in plain code, so no solver is needed **(new)**. HiGHS arrives with the Phase 3 transfer planner.
- `prediction` is a pure function: a data snapshot plus a set of overrides in, an xP/xMins table out (per Footballer, per Gameweek, per fixture). No database access, no clock and no network inside it. Jobs build the snapshot and store the table.
- Captain, vice-captain, XI, bench, P(needed) and the Mini-league state are pure functions in `advice` over the xP table, the Member's Squad and reference shares. Delivery renders them in fixed templates in `texts.py`.
- `explain` holds the only Claude client: one adapter behind a protocol, with a fake for tests. Nothing else imports the Anthropic SDK.

The xP model (ticket 20)

- **Shape:** a model built from parts in AIrsenal's style, with these steps:
  - team expected goals for and against per fixture;
  - each Footballer's share of team goals and assists;
  - expected minutes;
  - point components: appearance, goals, assists, clean sheet, goals conceded, saves, bonus, defensive contribution and cards, scored with each season's own position rules.
- **Method:** Poisson rates, with per-90 rates shrunk toward position and club priors. NumPy and SciPy only, with no ML framework.
- **Team strength:** attack and defence ratings fitted from football-data.co.uk results, closing odds and (from 2026/27) match xG, blended with FPL's xG and xGC. Home advantage is one global term **(new)**. Upcoming fixtures are rated from team strengths, not from bookmaker prices for those fixtures.
- **Minutes:** expected minutes = start probability × expected minutes if started. The inputs are:
  - recent starts and minutes;
  - `chance_of_playing_next_round` and `chance_of_playing_this_round`;
  - the `status` flag;
  - rotation risk from fixture congestion;
  - lineup stability.

  Scout overrides plug in here and nowhere else.
- **Priors early in the season:** prior-season per-90 rates come from FPL's `element-summary/{id}` `history_past`, matched across seasons by FPL's stable Footballer `code`. They are fetched once a season, about 700 requests at the sampler's low priority **(new)**. The `footballers` table gains `code`.
- **Horizon:** raw xP is stored for 5 Gameweeks. Phase 2 advice uses only the next Gameweek. The decayed 5-Gameweek sum (decay 0.85) is computed and stored for Phase 3 but not shown **(new)**.
- **Baseline:** FPL's `ep_next`, rescaled, blended with a last-5 average. It is always computed. It is the fallback and the reference.
- **When it runs:**
  - after `gw_final` completes;
  - daily at 06:30 UK, after the 06:00 football-data.co.uk fetch;
  - at deadline −90 minutes, right after the Scout overrides job.

  Each run writes the table, keyed by season, a run ID, Gameweek and Footballer, and marks it current. The last 2 runs plus the deadline −90 run of each Gameweek are kept for accuracy reports; older runs are pruned **(new)**.
- **Core or Baseline:** a setting chooses which model the advice uses. It ships set to Baseline and moves to Core only after the backtest bar is met. The owner makes that change in a PR that records the backtest result **(new)**. Advice text names the model in use.

Backtest (ticket 20)

- An owner and contributor CLI, `python -m fplbot backtest`. It downloads two sources into a git-ignored local cache at run time, and neither is ever committed:
  - vaastav's per-Gameweek history for 2024/25 and 2025/26, which includes FPL's own per-Gameweek expected points as the `ep_next` reference;
  - the football-data.co.uk season CSVs.
- **Walk-forward:** a prediction for Gameweek k uses only data available before Gameweek k's deadline. Settings are tuned on 2024/25 only, and 2025/26 is the untouched check.
- **Metrics:** MAE and Spearman rank correlation over Footballers with at least one appearance in the window. The secondary view is OpenFPL's 0–2 versus 3+ point buckets. Horizons 3, 5 and 8 are reported; the default moves only on a clear win.
- **Bar to ship:** beat `ep_next` on both MAE and rank correlation in each season separately. The report is written to a Markdown file the owner pastes into the switch-over PR.
- CI runs the backtest code path on a tiny synthetic fixture season to keep it working, never against real downloaded data.

Captain and bench (ticket 21)

- **Inputs:**
  - the last-deadline Squad, with a caveat while the coming Gameweek's picks are hidden;
  - the current xP table;
  - Elite shares (top 10k for Members ranked in the top 100k, otherwise top 100k **(new)**);
  - Rival shares and history.
- **Free Hit:** if the last-deadline picks used a Free Hit, the advice uses the picks from the Gameweek before it **(new)**.
- **Captain:** highest next-Gameweek xP. Options within the 0.3 tie band are tied. When the Goal is Overall rank, a tie is broken by the higher Elite captain share; if that is missing or stale, by xP, and the message says so. There is no EO risk term.
- **Vice-captain:** the best-xP starter from a different match, with start probability ≥ 0.85. If the captain has a double Gameweek, the vice-captain is the next best Footballer who passes that rule.
- **XI:** the maximum xP over legal formations (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD).
- **Bench:** the backup goalkeeper is the sub goalkeeper. Outfield subs are ordered by P(needed) × xP-if-plays. P(needed) is computed in plain code from start probabilities and formation legality, with no simulation. A starter with start probability below 0.5 that no legal autosub can cover triggers a warning **(new threshold)**.
- **Mini-league state:**
  - z = L / (σ√n) against the nearest Rival above and the nearest below in the Goal league.
  - σ is the empirical standard deviation of the weekly points difference, shrunk toward 15 when fewer than 8 Gameweeks exist.
  - Ahead is z ≥ +1, Behind is z ≤ −1, Close otherwise, and Hopeless is z ≤ −2 with n ≤ 4.
  - Ahead: match the Rivals' most common captain within the tie band.
  - Behind (n ≤ 6): offer a captain the leading Rival lacks, within 10% of the top xP, labelled a variance choice.
  - Hopeless: say so and suggest switching the Goal to Overall rank.
  - The Mini-league Goal changes the captain only.
- **Rival history:** the per-Gameweek points of the nearest Rival above and below, fetched from `entry/{id}/history` after `gw_final` for Members whose Goal is Mini-league. Kept for the season and deleted with the league, like Rival picks **(new)**.
- **Chips:** none assumed. The functions take a chip-active flag (Triple Captain at 3×, Bench Boost orders the bench as starters) for Phase 3, and Phase 2 always passes "none".
- **Commands:** `/captain` shows the top 3 captains, the vice-captain and the tie-break or Goal-risk line. `/bench` shows the XI, the bench order with P(needed) and any autosub warning **(new split)**. Both use one header: Gameweek, "based on your GWn Squad", and the model in use.

Gap (ticket 19)

- The same `advice/gap.py` formula and thresholds. The jobs pass next-Gameweek xP from the model in use as the weight, in place of the last-4 average. The header says "weighted by xP (Core)" or "weighted by xP (Baseline)". The old recent-points weight is removed, not kept as an option **(new)**.

Scout overrides (tickets 10, 22)

- **Inputs:** the existing `footballer_news` log, which gains `chance_of_playing_this_round` and `chance_of_playing_next_round`, still written only on change. Before relying on FPL's newer `scout_risks` and `scout_news_link` fields, check that they are present and parseable.
- **Regex parser:** a pure function from FPL's templated news text (for example "Hamstring injury - 75% chance of playing", "Suspended until …", "Expected back …") to overrides on start probability and minutes-if-started. Live from day one.
- **Leftovers:** at deadline −90 minutes, the news lines changed this Gameweek that the regex didn't parse go to Claude in one synchronous call, but only if there are any. The input is Footballer ID, name, club and news text, nothing else.
- **Claude output:** must parse against the strict schema: a list of {Footballer ID from the input, minutes-if-started change, start-probability change, confidence low/medium/high}. Anything else is dropped and logged, and nothing is retried.
- **Shadow:** each Gameweek stores xMins and xP three ways: no overrides, regex overrides, and regex plus Claude overrides. They are scored against actual minutes and points once the Gameweek is final. Claude-derived overrides apply to advice only once they beat the no-override baseline on minutes MAE over at least 8 Gameweeks with at least 30 affected Footballer-Gameweeks **(new minimum)**. The owner switches them on by hand. If they never qualify, the Claude parsing path is deleted.
- **Member notes:** `/note <text>`, at most 500 characters and 3 per Gameweek.
  - The note goes to Claude with the same schema and the same input rule: the note text plus a list of candidate Footballers, and no Member ID.
  - The result is stored as a per-Member overlay that expires at the next deadline. `/note` with no text lists the active notes, and `/note clear` removes them.
  - Notes count as Claude-derived, so while those are off the reply says the note is recorded for testing and doesn't change advice yet.
  - Member advice is recomputed on demand for that Member only, using the shared table plus the overlay.
  - Notes are Member data: deleted on `/leave`, excluded from the shared job, never logged, and included in the encrypted backup.

`/why` and Claude (ticket 22)

- **Model:** Sonnet 5.5 (`claude-sonnet-5-5`) through the Anthropic API with `ANTHROPIC_API_KEY`, which is optional. One fixed system prompt, no prompt caching engineering, no tools.
- **`/why captain|bench|gap`:** with no argument it defaults to captain **(new)**. It recomputes the matching advice and sends Claude only the structured result: Footballer names, numbers and tags. The reply is the templated advice followed by Claude's paragraph.
- **Fallback to the plain template:** used when there's no key, the call errors or takes more than 20 seconds, the spend limit is hit, the daily cap is reached, or the reply fails the numbers guard. The guard fails a reply that names a Footballer or number not in the input, or runs over about 120 words. There is no retry loop, and the Member is never told why the fallback was used.
- **Cap:** 5 `/why` calls per Member per UK day, counted in the existing usage store.
- **Spend:** a hard monthly limit set in the Anthropic Console (owner runbook step) plus an in-app monthly token ceiling that turns Claude off and DMs the owner once **(new)**.
- **Privacy:** no Member identifiers, team names or chat IDs in any prompt. Prompts and replies are not logged; only counts and token totals are. `PRIVACY.md` and the secrets runbook are updated before the first Claude call ships: they name Anthropic as a processor for `/note` text and `/why` inputs.

Sources and ingestion (ticket 13)

- **football-data.co.uk:** a new fail-soft adapter fetches the current season CSV daily at 06:00 UK through the existing polite client: generic User-Agent and its own 1 req/s limit, since it's a different host. Only derived aggregates are stored (team ratings and per-fixture expected goals), never the raw CSV. If it's down, the last ratings are kept, and the owner gets one DM after 2 days.
- **FPL additions:**
  - `event/{gw}/live` rows gain `defensive_contribution`, `yellow_cards`, `red_cards`, `own_goals`, `penalties_missed` and `penalties_saved`.
  - `bootstrap-static` gives `ep_next`, `chance_of_playing_*` and set-piece order (`penalties_order`, `direct_freekicks_order`, `corners_and_indirect_freekicks_order`). Captured at each xP run's snapshot.
  - Per-Gameweek `ep_next` is stored at the deadline −90 run for the accuracy report.
- Everything else follows Phase 1's ingestion rules: shared limiter priorities, idempotent jobs with completion rows (`xp`, `scout`, `odds`), and startup catch-up for the current Gameweek. A missed morning run is simply redone; a missed deadline −90 run is redone if the deadline hasn't passed.

Storage and privacy

- **New tables, all with a season column:** team ratings, xP runs and their per-Footballer/Gameweek/fixture rows, Scout overrides (source regex/Claude, Gameweek, Footballer, changes, confidence), Scout shadow scores, Member notes and their overlays, Rival history, and Claude usage counters.
- **Member notes and overlays** are the only new Member data: hard-deleted on `/leave` and cleared at rollover. Everything else is about Footballers or the bot's own predictions, not Member behaviour.
- **No Member telemetry:** nothing records which captain a Member chose or whether they followed advice. The captain report compares the bot's pick with public figures only.
- **Neon free tier:** xP tables are about 700 Footballers × 5 Gameweeks × a few runs. Pruning keeps them small. Writes are batched per run.

Operations

- **`/status` adds:** the last xP run (time and model), the next scheduled runs, whether Claude is configured, the Scout leftover count this Gameweek, `/why` calls today, and the month's Claude token total.
- **`/accuracy` gains:**
  - `xp`: per Gameweek and season to date;
  - `captain`;
  - `scout`.

  The existing Price-alert view moves to `/accuracy price`, and plain `/accuracy` lists the four.
- **Owner DMs**, through the existing deduplicated incident path: xP job failure, odds source down 2 days, the Claude monthly ceiling reached, and the backtest bar status changing.
- **The runbook gains:** setting `ANTHROPIC_API_KEY` as a sealed Railway variable, setting the Console spend limit, running the backtest, and the Core switch-over PR checklist.

## Testing Decisions

- **The seam stays the delivery boundary** (the Phase 1 harness). Tests send Telegram updates and scheduled-job ticks into the running bot with:
  - a fake clock;
  - recorded FPL fixtures;
  - a recorded football-data.co.uk CSV fixture;
  - a fake Claude adapter, scriptable to answer, error, time out or reply with invented numbers;
  - a real throwaway Postgres.

  They assert only on messages received and externally meaningful rows, such as `/leave` removing notes.
- **The xP model** is the one place a second seam is justified: a pure-function test seam with small hand-built snapshots that check its invariants:
  - blanks give 0 and doubles sum;
  - a zero start probability gives zero xP;
  - point components follow each season's rules;
  - shrinkage pulls low-minute Footballers toward the prior;
  - the output is deterministic for a fixed input.

  This is the approved exception to "one seam": the backtest needs the same function, and its correctness isn't visible through Telegram. **(new)**
- **Captain and bench scenarios through the delivery seam:**
  - a clear captain;
  - a tie broken by Elite share;
  - a tie with stale Elite data;
  - the vice-captain rule with a double Gameweek;
  - each Mini-league state: Ahead, Close, Behind with a differential, Behind without one, and Hopeless;
  - Free Hit reversion;
  - the hidden-picks caveat;
  - bench order with a doubtful starter;
  - the uncoverable-blank warning;
  - Baseline-model labelling.
- **Gap:** the same Phase 1 scenarios with the xP weight, plus the header label.
- **Scout:**
  - regex cases from real FPL news templates (recorded strings);
  - leftovers sent to the fake Claude only when present;
  - schema rejection;
  - shadow rows written and scored after `gw_final`;
  - Claude overrides not applied while off.
- **`/note`:** limits, expiry at the deadline, listing and clearing, per-Member isolation (another Member's advice unchanged), the "testing only" reply, and deletion on `/leave`.
- **`/why`:**
  - normal prose;
  - fallback on no key, error, timeout, invented number, invented Footballer and too many words;
  - the daily cap;
  - no Member identifiers in the captured prompt.
- **Jobs:** the xP run at each trigger, idempotent re-runs, startup catch-up, odds source down for 2 days leading to one owner DM, and xP job failure leading to one owner DM.
- **Backtest:** the CLI path on a synthetic season in CI, and its report format.
- **Prior art:** the Phase 1 harness (`tests/harness.py`), its FPL fixtures and the `_settle` timing fix. The ~11-minute suite is near the limit, so the new tests share fixtures and avoid per-test re-seeding where they can.
- **CI gate:** unchanged. These tests run on every PR with no secrets and no network.

## Out of Scope

- Transfer planner, hits, rolling free transfers, team value and the chip planner (Phase 3). The HiGHS solver and the `optimisation` module.
- Any advice that assumes an active Chip, though the chip-active flag exists for Phase 3.
- Autopilot and Ghost Squads, including the Baseline Ghost Squad (Phase 4). Phase 2 computes the Baseline, but no Ghost Squad plays it.
- The Odds API adapter (opt-in, needs a key). Revisit only if football-data.co.uk proves too stale.
- A scheduled per-Member brief, push advice or any Claude text outside `/why`. Claude in Price alerts, captain or bench messages.
- Prompt caching engineering and the Batch API.
- Web dashboard (open ticket 24).
- Any FPL login or write action. Member telemetry or feedback collection.
- Live, in-match updates.

## Further Notes

- **Scoring rules differ by season:** defensive contribution points started in 2025/26, so the 2024/25 backtest must score with that season's rules. Point components take the rules as an input rather than hard-coding the current season.
- **vaastav** no longer updates weekly (2026/27 stops at GW6). It's used only for the two finished backtest seasons, never at run time, and never committed (the data belongs to FPL and Understat).
- **The bot went live mid-season,** so the current season's per-Gameweek stats come from the Phase 1 launch backfill. Prior-season priors come from `element-summary` `history_past`, not from stored stats (Footballer IDs are renumbered each season; `code` is the stable key).
- **Claude model:** ticket 08 had recommended Haiku 5.5 for cost. The architecture ticket, the map and ticket 22 later settled on Sonnet 5.5. This spec follows the later decision. Spend stays tiny either way: only Scout leftovers once a Gameweek and at most 5 `/why` calls a day per Member.
- **Phase 1 review leftovers** worth doing first, because Phase 2 adds to the same files:
  - split `delivery/member_flow.py` and `sources/fpl.py`;
  - key the Watch list on the Member number;
  - remove the stale `ANTHROPIC_API_KEY` "not used in Phase 1" wording in the runbook and `.env.example`.
- **Rough ticket breakdown** for `/implement-spec`, in order:
  1. Phase 1 leftovers above;
  2. extra FPL fields, `code` and `history_past` priors;
  3. football-data.co.uk adapter and team ratings;
  4. xP model (pure) plus the Baseline;
  5. backtest CLI;
  6. xP job, storage and `/status`;
  7. Gap switches to the xP weight;
  8. `/captain` (Overall rank);
  9. Mini-league captain state and Rival history;
  10. `/bench` and P(needed);
  11. regex Scout overrides and the shadow;
  12. Claude adapter, guardrails and `/why`;
  13. Claude Scout leftovers;
  14. `/note`;
  15. `/accuracy xp|captain|scout`;
  16. `PRIVACY.md`, runbook and Core switch-over checklist.

  Tickets 4 and 5 can run beside 2 and 3. Tickets 7–10 need 6. Tickets 13 and 14 need 12.
