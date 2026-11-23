# FPL official API: what's in it and what it allows (2026/27)

Researched 2026-11-19 for ticket `issues/01-fpl-official-api.md`. Live probes were run that day with anonymous `GET` requests (generic user agent, no cookies, no login), roughly 120 requests in total, spaced out.

Evidence labels used below:

- **[Verified-live]**: observed directly in the live API response or headers on 2026-11-19.
- **[Verified-source]**: read in the FPL web app's own shipped JavaScript (`fantasy.premierleague.com/assets/*.js`), the official terms, or an official Premier League article.
- **[Community]**: reverse-engineered or reported by third parties, not confirmed by FPL.
- **[Inference]**: my conclusion from the above.

Timing note: on 2026-11-19, **Gameweek 10 is `is_current` and Gameweek 11 is `is_next`**, with the GW11 deadline at 2026-11-21 11:00 UTC. The international break means it is GW10/11 now, not GW12. [Verified-live]

## TL;DR

- **Everything the bot needs for Advice mode is public and needs no login.** That covers bootstrap-static (Footballers, prices, `news`, transfers in/out, plus the new price-predictor fields), fixtures, `event/{gw}/live`, `dream-team/{gw}`, `element-summary/{id}`, any Manager's `entry/{id}`, `history`, `transfers` and post-deadline `picks`, and classic and head-to-head league standings and matches. [Verified-live]
- **Login is needed only for a Manager's own private state.** That means `my-team/{id}` (current unsaved Squad, free transfers, chip status, selling prices), `entry/{id}/transfers-latest/`, `watchlist/{id}/` and `me/`, and every write. Login now goes through Premier League account SSO (PingOne OIDC at `account.premierleague.com`) and sends an `X-API-Authorization: Bearer <access_token>` header. The old cookie or password-POST login recipes no longer apply. [Verified-source + Community]
- **A Rival's Squad is only visible after the deadline.** `entry/{id}/event/{gw}/picks/` returns 404 for the upcoming Gameweek, so Rival gaps and Elite gaps can only be computed on the locked Gameweek. [Verified-live]
- **New in 2026/27, FPL publishes its own Price change predictor in the public bootstrap-static.** Each Footballer carries `price_change_percent`, `price_change_hourly_rate`, `price_change_projections` (the next 3 nightly deadlines, each with a likelihood from -5 to +5), `price_change_locked_until` and `price_change_calibrating`. The new `/api/stats/price-changes/` lists actual Price changes. Price alerts can be built on official data rather than our own model. [Verified-live + Verified-source]
- **No published rate limit, and none was hit.** A 30-request burst with no delay returned all 200s with no rate-limit headers. Responses come through a Google/Fastly (Varnish) CDN with edge TTLs from 60 s to 14 days, so polling faster than about 60 to 300 s buys nothing. [Verified-live] Community reports of 403 blocks for aggressive scraping exist, but no thresholds are known. [Community]
- **The terms forbid exactly what we would do.** FPL Terms clause 28(d) says a player shall not "use automated systems to access the Game and extract information from the Game". Clause 29 claims Premier League IP in "any Game data", and 28(b) bans commercial exploitation. There is no public API licence. A non-commercial open-source project is tolerated in practice, since a large ecosystem does this openly, but it is not permitted on paper. [Verified-source; tolerance is Inference]
- **The terms also undercut the Sandbox account idea.** Clause 6 bans individuals from registering multiple accounts and from giving anyone else access to their account (see also clause 27). Autopilot on a throwaway account, or the bot logging in as a Member, both conflict with the terms. [Verified-source]
- **The 2026/27 data model matches 2025/26 for chips and transfers.** There are 8 chips (WC, FH, BB, TC per half; first set expires at the GW19 deadline), up to 5 banked free transfers (`max_extra_free_transfers: 4`), no AFCON-style December top-up this season, and defensive contribution points retained. [Verified-live + official article]
- **Several 2026/27 timing changes affect the data.** Gameweek scores lock at 09:00 UK time the day after the last match, instead of 1 hour after it. Ranks and mini-leagues now update live, via edge-merged real-time fields. Projected bonus is shown from minute 20. BPS was reworked. [Official article; live-merge Verified-live]

## Detailed findings

### 1. Endpoints

Base URL: `https://fantasy.premierleague.com/api/`. Trailing slashes matter, and unknown paths return HTML 404. The endpoint list below combines live probes with the path templates found in the FPL web bundle `assets/index-DZSbhisR.js` [Verified-source].

#### Public (no login), probed live on 2026-11-19 [Verified-live]

| Endpoint | What it gives | Edge cache (`edge-control`) |
|---|---|---|
| `bootstrap-static/` | `events` (38 GWs: deadlines, `is_current`/`is_next`, `finished`, `data_checked`, `chip_plays`, `most_captained`, `transfers_made`, `ranked_count`), `teams` (20), `elements` (672 Footballers), `element_types` (squad limits per position), `element_stats`, `chips`, `phases` (months), `game_settings`, `game_config` (rules + **full scoring table** + price-change deadlines), `total_players` (11,303,494). About 174 KB gzipped. | `max-age=300` (also in `cache-control`) |
| `fixtures/` and `fixtures/?event={gw}` | 380 fixtures with kickoff, `team_h/a_difficulty` (FDR), scores, `finished`/`finished_provisional`, and per-fixture stat lists (goals, assists, bonus, BPS, saves, cards). | 300 s |
| `fixture/{id}/stats/` | Per-player stat lines for both sides of one fixture. | n/a |
| `event/{gw}/live/` | Per-Footballer `stats` for the GW plus `explain` (points breakdown per fixture). Empty `elements` before the GW starts. | 86,400 s for a finished GW |
| `event-status/` | Per-day `bonus_added` and points status (`"r"`), and a `leagues` update state. Good for checking whether the GW is final. | 300 s |
| `dream-team/{gw}/` | Top XI of the GW and the `top_player`. | 60 s |
| `element-summary/{id}/` | Upcoming `fixtures` with difficulty, per-match `history` this season (including `value`, `selected`, `transfers_in/out` per GW) and `history_past` per season. | 60 s |
| `entry/{id}/` | Manager profile, overall/GW points and rank, `last_deadline_bank`/`value`/`total_transfers`, and all leagues joined with ranks. **Includes the Manager's real first and last name and region.** | real-time merged (`x-ism-edge-merge: rt_merged`) |
| `entry/{id}/history/` | Per-GW points, rank, `percentile_rank`, bank, value, `event_transfers`, `event_transfers_cost`, `points_on_bench`; `chips` played (name + GW); `past` seasons. | up to 14 days (1,209,600 s) |
| `entry/{id}/transfers/` | Every transfer made (in/out, costs, GW). | up to 14 days |
| `entry/{id}/event/{gw}/picks/` | Squad for a **past or current** GW: 15 picks with `position`, `multiplier`, `is_captain`/`is_vice_captain`, `active_chip`, `automatic_subs`, `entry_history`. **404 for the upcoming GW.** | up to 14 days |
| `leagues-classic/{id}/standings/?page_standings=N&page_new_entries=N&phase=P` | 50 rows per page, with `has_next`. Overall league is id 314. Page 2001 still worked, so depth was not capped in my probe. | real-time merged |
| `leagues-h2h/{id}/standings/` | H2H table: W/D/L, `points_for`, `total`. | n/a |
| `leagues-h2h-matches/league/{id}/?page=N&event=GW&entry=ID` | H2H fixtures and results. The `event` filter gives this GW's head-to-head opponent. | n/a |
| `stats/price-changes/` | **New:** actual Price changes (`element`, `event`, `changed_at`, `cost_before/after`). It covered about 6 weeks (338 rows, 2026-10-08 to 2026-11-19), so it looks like a rolling window. | no-cache |
| `stats/most-valuable-teams/`, `stats/best-classic-private-leagues/` | Leaderboards of Squad value and of the best large private leagues. | 60 s |
| `team/set-piece-notes/` | Per-club set-piece notes (mostly placeholders right now). | 86,400 s |
| `regions/` | Country list. | 300 s |

Notes:

- Element records also expose `news`, `news_added`, `status` (a/d/i/s/u), `chance_of_playing_this/next_round`, `ep_this`/`ep_next` (FPL's own xP), xG/xA/xGI/xGC and per-90 rates, `defensive_contribution`, `starts`, set-piece orders, `transfers_in/out(_event)`, `cost_change_*`, `selected_by_percent` and `scout_risks`. [Verified-live]
- `entry/{id}/cup/` and `event/{gw}/fixtures/` returned 404. `bootstrap-dynamic/` no longer exists. [Verified-live]

#### Login required [Verified-live 403/401-style body + Verified-source]

- `my-team/{entry}/` returns 403 `"Authentication credentials were not provided."` [Verified-live] It is the only source of a Manager's **current** Squad before the deadline, with `free_transfers`/`transfers` limits, chip availability and **selling prices**. Selling prices differ from `now_cost` because of `transfers_sell_on_fee: 0.5`. [Community; field list not verified this session]
- `entry/{id}/transfers-latest/` returns 403, and `watchlist/{id}/` returns 403. [Verified-live]
- `me/` returns `{"player":null,"watched":[]}` when anonymous. [Verified-live]
- Writes such as `transfers/`, `my-team/{id}/` (save picks), `entry-create/`, `entry-update/`, `entry-autopick/` and `league/{id}/...` appear as path templates in the bundle. [Verified-source]
- The auth mechanism in the bundle: the client reads an OIDC access token (oidc-client with refresh-token exchange) and sets ``X-API-Authorization: `Bearer ${token}` `` on API calls. [Verified-source] The SSO config in the page shell points at `https://account.premierleague.com` with PingOne (`api.pingone.eu`). [Verified-source]
- Community tools report that refresh tokens rotate on every use, access tokens are short-lived (hours), and copied tokens break mid-season (`invalid_grant`). Sources: [fantasypl/mcp PR #71](https://github.com/fantasypl/mcp/pull/71), [rishijatia/fantasy-pl-mcp](https://github.com/rishijatia/fantasy-pl-mcp/) and [Aminou973/fpl-bot PR #1](https://github.com/Aminou973/fpl-bot/pull/1). [Community]

### 2. Rate limits, caching, polite patterns

- **Observed:** no `X-RateLimit-*` or `Retry-After` headers appeared anywhere. A 30-request back-to-back burst against uncached `entry/{id}/` returned 30 × 200 at about 0.22 to 0.25 s each. [Verified-live]
- **CDN:** responses carry `via: 1.1 google, 1.1 varnish, 1.1 varnish`, `x-cache: HIT, HIT` and `age`. Origin `cache-control` is mostly `no-cache, no-store`, but the CDN honours `edge-control: max-age=…` (60 s for element-summary and dream-team, 300 s for bootstrap-static, fixtures and event-status, 86,400 s for finished live data, 14 days for entry history and picks). [Verified-live]
  - [Inference] The CDN is purged on data events, because GW10 data was present in 10-day-old cached history. Polling faster than the edge TTL returns the same bytes.
- **Language:** responses `vary: X-API-Language, Accept-Encoding`. [Verified-live]
- **robots.txt:** `https://fantasy.premierleague.com/robots.txt` returns the SPA HTML shell, so there is no robots file. [Verified-live]
- **What happens on abuse:** there is no official statement. Community reports describe 403 "access denied" blocks for heavy scraping, no published thresholds, and a recommendation to watch for an HTML body where JSON was expected. Sources: [Jentic FPL API page](https://jentic.com/apis/fantasy.premierleague.com/fantasy-premierleague), [fplstat data reference](https://james-leslie.github.io/fplstat/data-reference). [Community]
- **Polite pattern** [Inference]:
  - Run a single worker, about 1 request/s, with exponential backoff on 403, 429 or 5xx, or on an HTML body.
  - Fetch bootstrap-static at most every 5 min, and mostly once around 00:00 UK time plus once near the deadline.
  - Cache immutable data (finished GW live data, past picks and history) permanently.
  - Send `Accept-Encoding: gzip` and a fixed, honest, generic User-Agent.
  - Never run parallel fan-out during live matches.

### 3. Terms of use

Source: FPL Terms, served at <https://fantasy.premierleague.com/help/terms> and read from the app's `assets/Terms-*.js` bundle on 2026-11-19. The page is undated and says the terms can change at any time. [Verified-source]

- **Clause 28(d):** you shall not "use automated systems to access the Game and extract information from the Game".
- **Clause 28(b):** you shall not exploit information obtained through the Game for commercial purposes. Clause 28(c) bans "spamming or flooding".
- **Clause 29:** the Premier League owns all IP "including … any Game data". It must not be used "without the prior written consent of the Premier League". There is no reproduction or distribution of components of the Game or derivative works.
- **Clause 6:** only one Registration per user. Individuals may not register multiple accounts or give any other person access to their account. **Clause 27** repeats this: no sharing or transferring control of an account.
- **Clause 5:** registrations must not be made by agents or third parties.
- **Clause 13:** no commercial mini-leagues.

Premier League website terms at <https://www.premierleague.com/en/terms-and-conditions> [Verified-source]:

- Use is limited to private and personal use, with no commercial use.
- No reproducing, re-utilising or redistributing content, and no "creating a database".
- No deep links or framing without approval.

There is **no official public API, developer programme or data licence** for FPL. I found none, and community references describe the API as unofficial and undocumented. [Community; absence of evidence]

[Inference] Calling the API from a small, non-commercial, invite-only bot is a breach of 28(d) on paper. In practice it is tolerated: a large public ecosystem of open-source libraries, MCP servers and sites uses these endpoints openly, and I found no report of the Premier League taking action against an FPL API tool. The risk grows with commercial use, republishing bulk data, branding that implies affiliation, and load. A public repo is fine to host code. It should not redistribute data dumps.

### 4. 2026/27 rule and data-model changes

Sources: the official PL article "All you need to know about changes to FPL for 2026/27" (31 July 2026), the official "Price Change Predictor" article (18 Oct 2026), Fantasy Football Scout (20 July 2026), and live data.

- **Chips (unchanged from 2025/26):** two sets of WC, FH, BB and TC, one per half. In `bootstrap-static.chips` there are 8 entries with `start_event`/`stop_event` 1–19 and 20–38. WC and FH start at GW2, while BB and TC can be used in GW1. The first set must be used by the GW19 deadline (13:30 GMT Sat 2 Jan) and does not carry over. There is no Assistant Manager chip (`mng_*` scoring keys are all 0). [Verified-live + official]
- **Free transfers:** up to 5 banked (`max_extra_free_transfers: 4`). `transfers_cap: 20` is also in settings, but its meaning is undocumented. **No December top-up this season**: 2025/26's AFCON extra free transfers do not return, because AFCON moves to mid-2027. [Verified-live + official]
- **Scoring (live `game_config.scoring`):**
  - Goals: GKP 10, DEF 6, MID 5, FWD 4.
  - Clean sheet: GKP and DEF 4, MID 1.
  - Defensive contribution: 2 for DEF, MID and FWD; 0 for GKP. It is retained unchanged from 2025/26. The thresholds are not in the API.
  - Assist 3; long play 2 and short play 1.
  - [Verified-live] Whether the GKP goal value changed versus 2025/26 was not checked.
- **BPS rework:**
  - Clearances, blocks and interceptions now earn 1 BPS per 3, instead of per 2.
  - There is no longer a −1 for being tackled.
  - GK saves are reweighted: inside the box 3, any other save 2, +1 for a big chance saved.
  - BPS weights are not in the API (`bps: 0` in scoring).
  - [Official article + FFS]
- **Gameweek lockdown:** scores become final at **09:00 UK time the day after the GW's last match**, instead of 1 h after the final whistle. This allows late Opta reviews for BPS and defensive contribution. Use `events[].finished` + `data_checked` and `event-status` before treating a GW as final. [Official]
- **Live ranks and mini-leagues:** global and league positions now update continuously during matches, and projected bonus is added after 20 minutes. On the wire, `entry/{id}/` and `leagues-classic/.../standings/` are edge-merged with real-time fields (`x-ism-edge-rt-fields: summary_overall_points, summary_event_points, summary_event_rank, summary_overall_rank, league_entry_rank` and `standings, last_updated_data, new_entries`). [Official + Verified-live]
- **Price Change Predictor (new):**
  - Official description: progress towards a rise or drop is shown "as a percentage". Over 100% means the price is expected to change at the next 00:00 UK update. The page refreshes every 15 min, and a price can move up to £0.3m per Gameweek. The UI is behind login. [Official]
  - The underlying data is in the **public** bootstrap-static [Verified-live]:
    - `game_config.settings.price_change_deadlines` gives the next 3 midnights.
    - `game_config.status.price_change_last_updated` gives the last refresh time.
    - Per Footballer: `price_change_percent`, `price_change_hourly_rate`, `price_change_projections[{offset 0..2, projected_percent, likelihood}]`, `price_change_locked_until` (2 Footballers) and `price_change_calibrating` (1 Footballer).
  - The web app maps likelihood +5 to "Very likely to rise", +4 to "Likely to rise", −4 to "Likely to drop", −5 to "Very likely to drop" and anything else to "Unlikely to change". It shows "Unlocks in N days" when `price_change_locked_until` is set. [Verified-source]
  - The predictor only shows predicted progress "after a period of calibration of at least one Gameweek". [Official]
- **Other:** 11 Footballers were reclassified by position, so `element_type` should be re-read each season. Overall rank is also shown as a percentage (`percentile_rank` and `overall_rank_percentage` in history). [Official + Verified-live]

## Implications for the bot's design

1. **Advice mode needs no FPL login at all.** A Member provides only their FPL team ID.
   - Their own Squad comes from `entry/{id}/event/{current}/picks/` (the last locked Squad) plus `entry/{id}/transfers/`.
   - Free transfers banked are not public, so derive them [Inference] from `history.current[].event_transfers`, `event_transfers_cost` and `chips`: roll +1 per GW, cap at 5, and reset on WC or FH.
   - Selling prices are not public. Estimate them from purchase price (`transfers/`) and `now_cost` with the 50% sell-on rule (`transfers_sell_on_fee: 0.5`).
   - Show the bot's estimate, and let a Member correct it.
2. **The Price alert should consume FPL's own predictor fields** (`price_change_projections[0].likelihood` and `price_change_percent`) from bootstrap-static, rather than building our own net-transfer model.
   - Poll shortly before 00:00 UK time and again after it.
   - Use `stats/price-changes/` to confirm what actually changed.
   - Respect `price_change_calibrating` and `locked_until`.
3. **Gaps can only use locked data.**
   - A Rival gap or Elite gap reflects the Squads as of the current/last deadline, not what Rivals plan next.
   - An Elite cohort sample costs 200 standings pages plus 10,000 picks calls for top 10k, or 2,000 pages plus 100,000 picks calls for top 100k, per Gameweek.
   - The top-100k cohort is unrealistic to crawl politely at 1 req/s (about 28 h). Plan to sample it, use top 10k only, or take a third-party aggregate (a separate ticket).
   - Picks are cached at the edge for 14 days, so crawl once per GW after the deadline and store the result.
4. **Treat a Gameweek as final only after the 09:00 UK lockdown** (`finished && data_checked`). Before that, points are provisional and BPS may change.
5. **Read rules from `game_config` and `chips` rather than hard-coding them.** That covers scoring, squad limits, `max_extra_free_transfers`, chip windows and phases. It makes the 2027/28 rollover cheap.
6. **Autopilot is the main policy problem.**
   - A Sandbox account breaches clause 6 if its owner already has an FPL account.
   - Any automated write also hits 28(d).
   - Automation would need a fragile OIDC refresh-token flow with rotating tokens.
   - Recommendation: keep Autopilot out of scope, or limit it to a dry run that produces the transfer list for a human to enter.
   - Never ask Members for credentials or tokens: clause 27 forbids sharing account access.
7. **Keep load and footprint small and non-commercial.**
   - Use one shared cache for all Members.
   - Use a generic User-Agent and backoff.
   - Do not republish bulk FPL data in the repo or on a public site.
   - Show no Premier League or FPL branding.
   - Store minimal personal data: `entry/{id}` returns real names, so keep only team ID and team name for Rivals.
   - Note in the README that the API is unofficial and can change or break without notice.

## Open questions

- Exact `my-team/{id}` response shape for 2026/27 (`transfers.limit`/`made`/`bank`, `chips[].status_for_entry`, `picks[].selling_price`). This was not verified, because it requires login, which was out of scope.
- What triggers a 403 block, and at what rate. Not tested beyond a 30-request burst, deliberately.
- Whether `stats/price-changes/` is a fixed rolling window, and how long it is.
- The meaning of likelihood values ±1 to ±3, and of `price_change_hourly_rate` units. These are undocumented. The UI only distinguishes ±4 and ±5.
- Whether the Premier League would object to a named open-source "FPL" bot. There is no precedent either way. Low priority for a private, invite-only, non-commercial group.
- Whether 2025/26 already had GKP goals at 10. Not checked; only matters for historical training data.

## Sources

Live API (anonymous GET, 2026-11-19):

- https://fantasy.premierleague.com/api/bootstrap-static/
- https://fantasy.premierleague.com/api/fixtures/ (also `?event=11`), https://fantasy.premierleague.com/api/fixture/1/stats/
- https://fantasy.premierleague.com/api/event/10/live/, https://fantasy.premierleague.com/api/event/11/live/, https://fantasy.premierleague.com/api/event-status/, https://fantasy.premierleague.com/api/dream-team/10/
- https://fantasy.premierleague.com/api/element-summary/411/
- https://fantasy.premierleague.com/api/entry/1/, `/entry/1/history/`, `/entry/1/transfers/`, `/entry/1/event/10/picks/`, `/entry/1/event/11/picks/` (404), `/entry/1/transfers-latest/` (403), `/entry/1/cup/` (404)
- https://fantasy.premierleague.com/api/leagues-classic/314/standings/ (pages 1, 200, 2001), https://fantasy.premierleague.com/api/leagues-h2h/181117/standings/, https://fantasy.premierleague.com/api/leagues-h2h-matches/league/181117/?event=10
- https://fantasy.premierleague.com/api/stats/price-changes/, `/stats/most-valuable-teams/`, `/stats/best-classic-private-leagues/`, `/team/set-piece-notes/`, `/regions/`
- https://fantasy.premierleague.com/api/my-team/1/ (403), `/watchlist/1/` (403), `/me/`
- https://fantasy.premierleague.com/robots.txt (no robots file; returns SPA shell)

FPL web app source and official pages:

- FPL web bundle (endpoint templates, `X-API-Authorization` header, predictor UI logic): https://fantasy.premierleague.com/assets/index-DZSbhisR.js
- FPL Terms (clauses 5, 6, 13, 27, 28, 29): https://fantasy.premierleague.com/help/terms (text from https://fantasy.premierleague.com/assets/Terms-DUOzP1QV.js)
- FPL Rules page bundle (chip effects): https://fantasy.premierleague.com/assets/Rules-2TOq7oH5.js
- Premier League website terms: https://www.premierleague.com/en/terms-and-conditions
- Official: "All you need to know about changes to FPL for 2026/27" (31 Jul 2026): https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627
- Official: "What's new in 2026/27 Fantasy: Price Change Predictor" (18 Oct 2026): https://www.premierleague.com/en/news/4680462/whats-new-in-202627-fantasy-price-change-predictor

Community and secondary:

- Fantasy Football Scout, "FPL 2026/27: 5 rule changes + new features announced" (20 Jul 2026), for BPS detail and lockdown: https://www.fantasyfootballscout.co.uk/2026/07/20/fpl-2026-27-5-rule-changes-new-features-announced
- fantasypl/mcp PR #71 (PingOne OIDC, `X-Api-Authorization`, rotating refresh token): https://github.com/fantasypl/mcp/pull/71
- rishijatia/fantasy-pl-mcp (refresh token rotation/revocation): https://github.com/rishijatia/fantasy-pl-mcp/
- Aminou973/fpl-bot PR #1 (`invalid_grant` failures mid-season): https://github.com/Aminou973/fpl-bot/pull/1
- Jentic FPL API page (no documented rate limits): https://jentic.com/apis/fantasy.premierleague.com/fantasy-premierleague
- fplstat data reference (unofficial endpoint docs): https://james-leslie.github.io/fplstat/data-reference
