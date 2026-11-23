# Spec: Phase 1, Squad, Rival and Elite gaps, and the nightly Price alert

Type: spec
Status: open
Labels: ready-for-agent
Assignee: —
Blocked by: —

Source: [map](../map.md), with every decision taken from the resolved tickets 01, 03, 04, 12, 13, 14, 15, 16, 19, 23 and ADRs 0001-0003. Vocabulary follows [GLOSSARY.md](../../../GLOSSARY.md).

## Problem Statement

A small group of invited Fantasy Premier League Managers wants to see how their Squad differs from the Managers they care about, and to avoid paying more than necessary when Footballers change price. Today they have to dig through FPL screens and third-party sites by hand. Elite ownership data cannot be reused from any outside publisher, FPL hides picks until the deadline, and price movements happen at 00:00 UK when nobody is watching. They want a Telegram bot that tells them, without ever asking for their FPL password.

## Solution

An invite-only Telegram bot, running in Advice mode on public FPL data only. A Member joins with a single-use invite, links their FPL team ID, picks a Goal and a timezone, and then:

- sees their own Squad as of the last deadline;
- sees their Rivals and a league progress view for their Followed leagues;
- sees their Elite gap and Rival gap on demand, with freshness and margin of error always stated;
- manages a Watch list;
- gets one plain-text Price alert a night (default 20:00 local), and nothing on quiet nights;
- can leave at any time and have all their data deleted.

The owner gets operational DMs, a read-only `/status`, and an owner-only `/accuracy` report on the Price-alert predictor. There is no Claude call anywhere in Phase 1.

## User Stories

Joining and leaving

1. As the owner, I want an owner-only `/invite` command that creates a single-use code and a `t.me` start link, so that only people I choose can use the bot.
2. As the owner, I want the Member count capped at 10, so that load and the FPL rate limit stay within bounds.
3. As a friend, I want to open the invite link and have my chat allow-listed immediately, so that I can finish setup later with `/start` if I get interrupted.
4. As a stranger without an invite, I want to get no response, so that the bot's existence is not advertised.
5. As a Member, I want to send my FPL team ID and be shown the team name, manager and rank with "Is that you?", so that I don't link the wrong team.
6. As a Member, I want a team already linked to another Member to be refused, so that nobody can impersonate someone else's Squad.
7. As a Member, I want to choose my Goal with buttons (Overall rank or Mini-league), so that I don't have to type.
8. As a Member choosing Mini-league, I want to see the private leagues my team is in and pick one, so that Rival advice targets the league I care about.
9. As a Member with no private league, I want to fall back to Overall rank automatically, so that setup never dead-ends.
10. As a Member, I want to switch my Goal at any point in the season, so that I can change focus when I fall out of overall contention.
11. As a Member, I want to pick my timezone from four buttons or type a city or zone, so that the Price alert arrives at my local time.
12. As a Member, I want any command to abandon the question the bot is asking, so that I am never trapped in a flow.
13. As a Member, I want stale buttons from old messages to be ignored with a polite note, so that I can't corrupt my settings by tapping an old keyboard.
14. As a Member, I want `/leave` to ask once and then hard-delete my Member data, so that I control my data.
15. As the owner, I want a used invite to stay used after the Member leaves, so that codes can't be reused.

Squad, Rivals and leagues

16. As a Member, I want to see my Squad as of the last deadline, so that I know what the bot is basing its output on.
17. As a Member, I want the message to say when GW picks are hidden until the deadline, so that I understand why my Squad looks old.
18. As a Member, I want to see my Rivals, defaulting to the nearest 2 above and 2 below me by rank in my Goal league, so that the list is relevant.
19. As a Member, I want `/rivals all` to show everyone in the Goal league, so that I can look wider.
20. As a Member whose Goal is Overall rank, I want Rivals taken from my Followed league, so that the feature still works.
21. As a Member in a head-to-head league, I want my opponent this Gameweek treated as a single Rival, so that H2H is covered.
22. As a Member, I want `/league` to show the table with rank movement arrows, points behind the Rival above, points ahead of the Rival below and the gap to the leader, so that I see my position at a glance.

Elite gap and Rival gap

23. As a Member, I want an Elite gap listing at most 3 Footballers I back that the Elite cohort mostly doesn't, and at most 3 the Elite backs that I don't, so that I see where I differ.
24. As a Member, I want the Gap measured by XI share and captain share, weighted by the Footballer's average points over the last 4 finished Gameweeks, so that the difference reflects how much it could swing points.
25. As a Member, I want `/gap captain` to show the captain part alone, so that I can see the biggest driver without it being buried.
26. As a Member, I want differences under 2x the margin of error, or under 0.35 points a Gameweek, to be hidden, so that I'm not shown noise.
27. As a Member who matches the template, I want to be told I look like the template, so that an empty result isn't confusing.
28. As a Member, I want no summed "net edge" number, so that I'm not misled by an incomplete Footballer pool.
29. As a Member, I want the header to show Gameweek, sample size and margin of error, so that I can judge reliability.
30. As a Member, I want a partial sample labelled as partial, so that I don't mistake it for the full figure.
31. As a Member, I want a previous-Gameweek figure to carry a warning, and never be mixed with the current one, so that I don't compare unlike data.
32. As a Member, when no Elite figures exist yet, I want to be told so and pointed to `/rivals`, so that I still get something useful.
33. As a Member, I want a Rival gap against the same formula, with a line showing how many Rivals share my captain, so that I see captaincy overlap.
34. As a Member, I want Gaps only when I ask, with no push messages, so that the bot is quiet.
35. As a Member, I want the Elite gap against the top 10k and the top 100k as separate cohorts, so that I can see both groups.

Watch list

36. As a Member, I want to add and remove Footballers on my Watch list, so that I get Price alerts for Footballers I'm considering.
37. As a Member, I want to see my Watch list, so that I know what is being tracked.
38. As a Member, I want an ambiguous Footballer name to ask me which one I mean, so that I don't watch the wrong person.

Price alert

39. As a Member, I want one plain-text Price alert a night at my chosen time, so that I get a single predictable message.
40. As a Member, I want the alert to default to 20:00 local and to change with `/time HH:MM`, so that I can fit it to my routine.
41. As a Member, I want `/time` to tell me when my choice is clamped to 17:00-23:15 UK, so that I know the real send time.
42. As a Member, I want Footballers I own listed only when Likely (+/-4) or Very likely (+/-5) to fall, so that I only see actionable falls.
43. As a Member, I want Watch-list Footballers listed only when likely to rise, so that I only see relevant rises.
44. As a Member, I want each line to show name, position, club, price and new price, a Very likely / Likely label and any injury or doubt flag, so that I can decide quickly.
45. As a Member, I want Very likely before Likely, then alphabetical, so that the most certain items come first.
46. As a Member, I want a one-line "tomorrow night" section only for Very likely changes, so that I get early warning without clutter.
47. As a Member, I want a Footballer listed tonight not repeated under tomorrow, so that nothing is duplicated.
48. As a Member, I want a savings line stating the 0.1m, with no transfer recommendation, so that I get facts and make my own decision.
49. As a Member, I want a caveat before deadlines, or whenever my Squad could be stale, saying the alert is based on my last-deadline Squad, so that I can ignore Footballers I've already sold.
50. As a Member, I want no message when there is nothing to report, so that silence means all clear.
51. As a Member, I want no message when data is missing or calibrating, so that I'm never sent wrong predictions.
52. As the owner, I want a single DM when a night's data failed, so that I know without Members being spammed.

Owner and operations

53. As the owner, I want `/accuracy` to show hit rate per likelihood code for tonight and tomorrow plus a season total, so that I can judge the predictor.
54. As the owner, I want a flag when +/-4 is below 70% or +/-5 below 85% over 14 nights with at least 20 predictions per bucket, so that I know when to raise the threshold by hand.
55. As the owner, I want a read-only `/status`, so that I can check health from Telegram.
56. As the owner, I want a DM on a 403 or on a second failure in a row, so that I react quickly.
57. As the owner, I want one deduplicated alert and a "recovered" message, so that I'm not flooded.
58. As the owner, I want the bot to ping an optional heartbeat URL every 5 minutes while healthy, so that my monitoring service detects outages.
59. As the owner, I want a nightly encrypted export of the Member tables sent to my Telegram chat, so that I have an off-platform backup.
60. As the owner, I want an owner-confirmed `/rollover` that starts a new season, so that data is separated by season.
61. As the owner, I want all FPL traffic limited to 1 request a second with a generic User-Agent, so that the bot is polite and leaks nothing about me.
62. As the owner, I want 403s never retried and 429/5xx retried with backoff and jitter, so that the bot doesn't hammer FPL or risk a block.
63. As the owner, I want jobs to be idempotent with startup catch-up, so that a restart or deploy never loses a Gameweek's data.
64. As a contributor, I want the bot to run locally with zero keys and a fake FPL source, so that I can develop without secrets.

## Implementation Decisions

Architecture (fixed by ADRs 0001-0003 and the architecture ticket)

- Modular monolith, one asyncio Python 3.14 process on the owner's Railway Hobby plan, with Neon Postgres. Telegram long polling, so no inbound HTTP. APScheduler with no persisted job store: jobs are rebuilt from the DB and FPL deadlines at startup and after each data refresh.
- Modules and dependency direction: delivery depends on advice, which depends on prediction and optimisation (unused in Phase 1), which depend on store, which depends on sources; jobs orchestrate all of them. Delivery is the only module that knows about chats.
- Gap, Rival selection and Price alert decisions are pure functions in `advice`. They take plain data and return decisions, and delivery renders them in fixed templates.
- No Claude call in Phase 1. The `explain` module is not exercised.
- Migrations run in Railway's pre-deploy command and stay backward-compatible. Every table carries a season column.

Sources and ingestion

- The FPL API is the only data source, with no login. The sources module exposes fail-soft adapters behind one shared rate limiter (at most 1 req/s; interactive commands and the Price alert have priority over the Elite sampler).
- One generic browser-style User-Agent, no personal details, URL or repo name. Conditional requests where ETag or Last-Modified is available. 429/5xx: exponential backoff with jitter, honouring Retry-After, at most 5 tries. 403: never retried, the job pauses until its next run and the owner is told.
- `bootstrap-static` is fetched when needed (price-archive times 18:00, 20:00, 22:00, 23:00, 23:45 UK; 00:05 with the `/stats/price-changes/` archive at 00:10; each distinct Price-alert time; hourly 08:00-23:00 for news changes; deadline -90 min, -30 min and just after; on demand when more than 15 minutes old) and is held in memory only.
- Post-deadline job starts at deadline +5 minutes with a cheap probe. While FPL answers "updating", wait 10 minutes and probe again (these waits do not count as backoff tries). Order: the 450 standings pages that fix the Elite cohorts (target: before first kickoff; if later, mark the run "read late"), then Member and Rival picks, then the Elite picks sample.
- Elite sampler: own stratified sample on the official API for the top 10k and top 100k cohorts at +/-2% (95%), roughly 4,400 requests and 73 minutes a Gameweek. Output per Gameweek and cohort and Footballer: ownership, XI share, captain share, EO, chip usage, sample size and margin of error. A partial sample is published if each cohort reached at least half its target, with recomputed margin of error; otherwise the previous Gameweek's figures are kept, labelled. The two are never mixed.
- Followed leagues: every Mini-league of each Member with at most 50 managers (de-duplicated across Members) plus the H2H opponent each Gameweek. A Goal league above 50: top 10 plus the 20 directly above and 20 directly below the Member.
- Once a Gameweek is final: fetch `event/{gw}/live` once, then refresh each Member's history and each Followed league's standings.
- Idempotent jobs, each writing a completion row per Gameweek (`elite`, `picks`, `gw_final`, plus `price_archive` per night). Startup catch-up covers the current and previous Gameweek. Missed evening snapshots are skipped, never back-filled.
- Launch backfill (going live at GW11 or later): `event/{gw}/live` for finished Gameweeks; Member history and past picks on join; no Elite backfill.

Storage and privacy

- Never stored: raw FPL responses and sampled Elite managers' IDs and picks (aggregates only).
- Kept across seasons: Footballers, clubs, fixtures, Gameweeks, per-Gameweek stats, a log of news and status changes (written only on change), Price changes, Elite ownership results, and price snapshots (5 a night: price, percent, hourly rate, the 3 likelihoods, lock flags).
- Rival picks are kept for the season and deleted when no Member follows that league. Member and Rival history is cleared at rollover. `/leave` hard-deletes immediately.
- No Member telemetry. No identifiers in logs. Unknown chats receive silence. Runtime secrets only in Railway sealed variables; no secret, and no FPL or third-party data, is committed.
- Neon free-tier limits (1 GB, 100 compute-hours, sleeps after 5 idle minutes) are binding: use the pooled connection string, short idle timeouts, and avoid needless writes.

Telegram flow (approved prototype, ticket 14)

- Owner-only `/invite` creates a single-use code plus a start link; redeeming allow-lists the chat; cap 10 Members; `/start` resumes an abandoned setup.
- Link step shows team name, manager and rank and asks for confirmation; a team already linked is refused.
- Goal by inline buttons. Timezone by four buttons plus "Other..." (typed city or zone). Any command abandons the open question; stale buttons are ignored politely. `/leave` asks once, then deletes.
- The prototype's pure bot module is the reference for conversation logic. It lives in the prototypes folder of this folder's parent and encodes the state machine more precisely than prose; implementers should read it before writing the flow.

Gap views (approved prototype, ticket 19)

- Edge per Footballer: (you start - reference XI share) x weight + (you captain - reference captain share) x weight, in points per Gameweek against the reference group. Weight in Phase 1 is the average points over the last 4 finished Gameweeks. The weight is a swappable input so Phase 2 can substitute xP without changing the formula.
- At most 3 Footballers per side. Hide a difference under 2x the margin of error or under 0.35 points a Gameweek. No net total.
- Header: Gameweek, sample size, margin of error, freshness. Partial, stale and not-ready states are labelled and never mixed.
- Rivals: nearest 2 above and 2 below by rank in the Goal league (Followed league when the Goal is Overall rank); `all` for everyone; H2H opponent as a single Rival. Between deadlines use the last-deadline Squad with a caveat. On demand only.
- `/league`: movement arrows, points behind the Rival above, ahead of the Rival below, gap to leader. No Ghost Squad row in Phase 1.

Price alert (ticket 15)

- Built on FPL's own price-change projection fields; no third-party predictor.
- Threshold: likelihood +/-4 or more. Owned Footballers for falls only, Watch-list Footballers for rises only. "Tomorrow night" line only for +/-5, and a Footballer already listed tonight is not repeated. Day 3 never shown.
- Format: one plain-text message. Header "Price alert · GW · tonight 00:00 UK"; sections "Likely to fall (you own)" and "Likely to rise (Watch list)" appear only if non-empty; Very likely before Likely, then by name; injury or doubt status shown on owned Footballers; one savings line; stale-Squad caveat on the night before a deadline or whenever the Squad could be stale.
- Timing: one alert a night at the Member's local time, clamped to 17:00-23:15 UK. Members sharing a time share one fetch. No second correction ping. No Wildcard or Free Hit logic.
- Silent when there is nothing to report or data is missing, absent, `price_change_calibrating` or unreachable. On a data failure the owner gets one DM that night; a failed fetch is retried once after 10 minutes, within the 23:15 cut-off.
- Accuracy: store the projection code at alert time beside the actual change from the 00:10 archive; hit rate per code for tonight and tomorrow plus a season total, read through owner-only `/accuracy`. Floors 70% (+/-4) and 85% (+/-5) over a rolling 14 nights with at least 20 predictions per bucket. Threshold changes are manual only.

Operations and delivery (tickets 16, 23, 12)

- Heartbeat to an optional `HEARTBEAT_URL` every 5 minutes while healthy. One deduplicated owner DM per incident with a "recovered" message. Nightly `age`-encrypted export of Member tables to the owner's chat. Owner-confirmed `/rollover`. Read-only `/status`.
- Delivery only through the PR-gated GitHub Actions pipeline (lint, types, unit and integration tests against a throwaway Postgres, gitleaks, CodeQL, pip-audit, Trivy, signed image, scoped Railway token, smoke check on a `ready sha=` log line, rollback on failure). No manual deploys.
- Apache-2.0 with NOTICE; `SECURITY.md`, `PRIVACY.md`, `.env.example` and a secrets runbook ship with Phase 1.

## Testing Decisions

- **One seam: the delivery boundary.** A test sends Telegram updates (messages, button presses, owner commands) and scheduled-job ticks into the running bot, with a fake clock, recorded FPL API fixtures behind the sources adapter, and a real throwaway Postgres. It asserts only on the messages the fake Telegram client receives and on rows that are externally meaningful (for example that `/leave` removed Member data). No separate seam for `advice`, store or sources.
- A good test exercises external behaviour only: what a Member or the owner sees, and when. It must not assert on module calls, SQL, internal state or scheduler internals, so refactors don't break it.
- Fixtures: recorded `bootstrap-static`, standings, picks, history and price-changes responses, including awkward cases (503 "updating", 403, 429, missing fields, `price_change_calibrating`, hidden picks, partial Elite sample, previous-Gameweek Elite figures).
- Scenarios to cover, mirroring the prototype's 11 walkthroughs: invite redeem, cap reached, team already linked, no private league fallback, timezone typed, abandoned flow, stale button, `/leave`; Gap with qualifying and non-qualifying differences, partial and stale freshness labels, no Elite data yet, between-deadline caveat; Rivals default, `all`, H2H, Goal league above 50; Price alert content, ordering, tomorrow line, caveat, clamping, silent night, data-failure owner DM; `/accuracy` flags; idempotent re-run and startup catch-up; rate limiting and 403 pause.
- Prior art: none in the repo yet (no code exists). The throwaway-Postgres service container in CI and the solver-regression test are described in the architecture ticket; the join-flow prototype's walkthroughs are the reference scenarios.
- CI gate: these tests run on every PR with no DB secrets.

## Out of Scope

- Xp model, captain and bench advice, Scout overrides, `/why` and any Claude call (Phase 2).
- Transfer planner and chip planner (Phase 3, not yet specified).
- Autopilot, Ghost Squads and the Ghost Squad row in `/league` (Phase 4).
- Web dashboard and its auth (open ticket 24).
- Any FPL login, password, or write action; any live-account automation.
- Member telemetry or feedback collection.
- A home-grown price predictor (only if FPL's fields disappear or stay miscalibrated).
- Live polling during matches, paid sources, and public open signup.

## Further Notes

- FPL reachability from Railway passed the probe (1,359 of 1,359 requests OK over 45 h), but standings mostly miss the CDN, so sample them sparingly and respect the 1 req/s ceiling.
- Weekly cadence matters: going live at GW11 or later means Elite figures only exist from the first post-deadline run after launch.
- Exact command names for Squad view and Watch list management were not fixed by the approved prototypes beyond those named above; the implementer should follow the prototype and keep names short and consistent with `/rivals`, `/gap`, `/league` and `/time`.
