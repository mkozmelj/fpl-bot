# FPL official API: what's in it and what it allows

Type: research
Status: resolved
Blocked by: —

## Question

What does the official Fantasy Premier League API (`fantasy.premierleague.com/api/...`) expose for the **2026/27** season, and what are we allowed to do with it?

- The endpoints we'd use: bootstrap-static (Footballers, prices, `news`, transfers in/out), fixtures, `entry/{id}`, `entry/{id}/event/{gw}/picks`, `entry/{id}/history`, classic and head-to-head league standings, `event/{gw}/live`, `dream-team`, and whatever else is useful.
- Which endpoints need no login, and which need an authenticated session.
- Observed rate limits and caching behaviour, what happens when you hit them, and polite request patterns.
- The Premier League / FPL terms of use on automated access and reuse of the data, including whether a public open-source project may call it.
- Rule changes in 2026/27 that change the data model (for example per-half chip sets or free-transfer top-ups).

Findings go in `.scratch/fpl-bot/research/01-fpl-official-api.md`.

## Answer

- Everything Advice mode needs is public with no login: bootstrap-static, fixtures, `event/{gw}/live`, `dream-team`, `element-summary`, any Manager's `entry/{id}` / `history` / `transfers`, classic and head-to-head standings, and H2H matches. Rival and Elite picks are visible only **after** the deadline (`picks` returns 404 for the upcoming Gameweek).
- Login is needed only for a Manager's own private state and for writes: `my-team` (current Squad, free transfers, chip status, selling prices), `transfers-latest`, `watchlist`, `me`. Auth is now PL account SSO (PingOne OIDC) with an `X-API-Authorization: Bearer` token and rotating refresh tokens, so it is fragile to automate.
- New for 2026/27: FPL's own Price change predictor is in public bootstrap-static (`price_change_percent`, `price_change_projections` with likelihood -5..+5 for the next 3 midnights, `locked_until`, `calibrating`), and `/api/stats/price-changes/` lists actual changes. Price alerts can use official data.
- There is no published rate limit, and none was hit in a 30-request burst. A Google/Varnish CDN caches responses for 60 s to 14 days, so polite polling at about 1 req/s with backoff is enough. A top-100k Elite cohort crawl (about 100k picks calls per Gameweek) is not polite, so sample it or use top 10k.
- FPL Terms 28(d) prohibits "automated systems to access the Game and extract information", and clause 29 claims IP in Game data. A non-commercial open-source bot is tolerated in practice but not permitted on paper: keep load low, do not redistribute data, and use no branding.
- Terms clause 6 (no multiple accounts, no sharing account access) conflicts with the Sandbox account / Autopilot idea and with ever handling Members' credentials.
- 2026/27 data model: 8 chips (one set per half, first set expires at the GW19 deadline), up to 5 banked free transfers, no December top-up, defensive contributions retained, BPS reworked, scores final at 09:00 UK the day after the last match, live ranks. Read all rules from `game_config` rather than hard-coding them.

Findings: [../research/01-fpl-official-api.md](../research/01-fpl-official-api.md)
