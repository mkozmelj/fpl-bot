# Free, legal football stats sources for predictions

Type: research
Status: resolved
Blocked by: —

## Question

Which free sources of football and FPL data can a **public open-source** project legally use as prediction inputs in 2026/27, and what does each give?

Candidates include Understat (xG/xA), FBref (check whether its advanced Opta-backed data still exists), the vaastav `Fantasy-Premier-League` GitHub dataset, FPL-Elo-Insights, ClubElo, football-data.org, bookmaker-odds APIs on free tiers (for example The Odds API), the official Premier League site, and any others found.

For each source, record:
- data offered and how fresh it is
- access method (API, CSV or scraping)
- licence or ToS position on scraping and redistribution
- rate limits
- reliability and maintenance status

Recommend a minimal v1 set and say which sources to avoid. Findings go in `.scratch/fpl-bot/research/02-free-stats-sources.md`.

## Answer

- **The FPL API is the core input.** It already carries per-Gameweek xG, xA, xGC, CBIT/defensive contribution, starts and set-piece order, so most of what Understat and FBref used to add is covered.
- **Minimal v1 set:** the FPL API, the football-data.co.uk season CSV (free; new 2026/27 match xG plus opening and closing 1X2, O/U and Asian-handicap odds), and optionally The Odds API's free plan (500 credits a month; the terms allow app display, storage and model training). Plus vaastav history for offline backtests only.
- **Avoid FBref.** Opta advanced data was removed in January 2026, the site is behind Cloudflare, and the terms forbid tools built on scraped data. **Avoid Understat** too: no API, no terms, the format changed in December 2025, and it is serving a maintenance page to scripted clients now.
- **ClubElo's API is effectively gone** (502, reportedly moved behind auth). FPL-Core-Insights' Elo columns are empty for 2026/27.
- **vaastav** (MIT code, data owned by FPL and Understat) no longer updates weekly: 2026-27 only reaches GW6. **FPL-Core-Insights** is fresh and rich but has no licence file, and its match stats are probably FotMob-derived. FotMob's ToS forbid redistribution, so use it for research only.
- **football-data.org's free plan** (10 requests a minute, delayed scores, no stats or odds) duplicates the FPL API, so skip it. Also avoid FotMob, Sofascore, WhoScored and premierleague.com scraping.
- **Design rule:** fetch third-party data at runtime into a local cache, never commit it to the public repo. Put each source behind a fail-soft adapter.

Findings: [../research/02-free-stats-sources.md](../research/02-free-stats-sources.md)
