# Free, legal football stats sources for predictions (2026/27)

Research for ticket `issues/02-free-stats-sources.md`. Checked on 2026-11-19. Per the FPL API, Gameweek 10 is the current (finished) Gameweek and Gameweek 11's deadline is 2026-11-21 11:00 UTC.

Labels used below:
- **[Verified]**: I checked it myself against the primary source (the repo, the file, the API response or the published terms) on 2026-11-19.
- **[Reported]**: comes from a secondary source or a community report that I could not confirm against the primary source.
- **[Inference]**: my own reading of the evidence.

## TL;DR

- **The FPL API is the base of Expected points (xP) and covers more than expected.** For each Footballer and each Gameweek it gives xG, xA, xGI, xGC, `defensive_contribution`, `clearances_blocks_interceptions`, `recoveries`, `tackles` and `starts`, plus set-piece order and injury news **[Verified]**. Most of what Understat and FBref used to add is already in it. Its ToS position is ticket 01's question.
- **Odds are the best free signal you can use legally.** football-data.co.uk publishes a free CSV for each season with opening and closing 1X2, over/under 2.5 and Asian-handicap odds. **New in 2026/27**, it also has match xG (`HxG`/`AxG`). It was updated through GW10 **[Verified]**. The Odds API's free plan gives 500 credits a month, and its terms allow use in apps, storage and model training. They only forbid reselling the data as a data product **[Verified]**.
- **FBref: avoid.** Opta cut off its advanced data (xG, progressive passes and so on) on 2026-01-20, and only basic stats remain **[Reported, consistent across sources]**. The site sits behind a Cloudflare challenge that blocks automated clients **[Verified]**. Sports Reference forbids building tools on data scraped from it **[Reported]**.
- **Understat: avoid as a dependency.** It still published 2026/27 xG (archived 2026-10-25), but it has no API, no published terms and no licence **[Verified]**. Its page format changed in December 2025 and broke the wrapper libraries **[Verified]**. Today it serves a "We will come back soon" page to a generic client **[Verified]**. vaastav stopped carrying Understat data after 2024-25 **[Verified]**.
- **ClubElo: no longer usable as an API.** `api.clubelo.com` returns 502 on every ratings path, and `/Fixtures` returns "Fixtures API deactivated" **[Verified]**. A community report says the API has moved behind authentication **[Reported]**. Even FPL-Core-Insights' `elo` column is empty for 2026/27 **[Verified]**.
- **vaastav `Fantasy-Premier-League`** is MIT-licensed code, but the README says the data belongs to FPL and Understat **[Verified]**. It no longer updates weekly: the 2026-27 folder only reaches GW6 **[Verified]**. Use it for **historical backtesting only**.
- **FPL-Core-Insights** (formerly FPL-Elo-Insights) refreshes several times a day and has rich player-level match stats (xG, xA, xGOT, CBIT, shots, xG by minute) **[Verified]**. It has **no licence file**, only an informal "use it however you like" **[Verified]**. Its match stats are probably taken from FotMob **[Inference]**, and FotMob's ToS forbid scraping and redistribution **[Verified]**. Fine for local research; don't make it a v1 runtime dependency.
- **football-data.org's free plan** covers the Premier League at 10 requests per minute, but it has only delayed scores, fixtures and tables. Lineups, stats and odds are paid **[Verified]**. FPL already gives us all of that, so skip it.
- **Recommended minimal v1 set:** (1) FPL API, (2) football-data.co.uk CSV, (3) optionally The Odds API free plan for upcoming-fixture odds. Plus vaastav history for offline backtests. **Avoid:** FBref, Understat, ClubElo's API, FotMob, Sofascore, WhoScored, and scraping premierleague.com.

## Detailed findings

### Comparison table

| Source | What it gives | Freshness (checked 2026-11-19) | Access | Licence / ToS position | Rate limits | Reliability / maintenance | v1 verdict |
|---|---|---|---|---|---|---|---|
| **FPL API** (`fantasy.premierleague.com/api/`) | Footballers, prices, ownership, fixtures, FPL difficulty ratings, per-Gameweek stats including Opta-derived xG/xA/xGI/xGC, CBIT/defensive contribution, starts, set-piece order, news | Live: GW10 finished, GW11 next | JSON, no key, no login | Undocumented. ToS are ticket 01's question | Not published | Official. The field set grew for the 2025/26 defensive-contribution rules | **Use (core)** |
| **football-data.co.uk** (`mmz4281/2627/E0.csv`) | Results, referee, shots, shots on target, corners, fouls, cards, **match xG (new in 26/27)**, 1X2 / O/U 2.5 / AH odds, opening and closing, from several bookmakers plus market max and average | 100 matches, through 2026-11-08 (GW10) | Free CSV download, no key | No licence or terms page found. Only a disclaimer. Credits its upstream sources | None published. Download once per Gameweek | Long-running (since the 2000s), updated twice a week. **Pinnacle columns dropped in 26/27** | **Use** |
| **The Odds API** | Pre-match odds for `soccer_epl`: h2h, totals, spreads, outrights. Player props (anytime scorer, shots, cards) from US bookmakers only | Live | REST JSON, API key sent by email | ToS (updated 2026-08-31) allow display in apps including commercial ones, indefinite storage and model training. They forbid reselling or redistributing the data as a standalone product. Attribution is optional | Free plan: 500 credits a month. Cost = markets × regions per call. Historical odds are paid-only | Commercial service | **Optional** (needs a key, so the maintainer has to sign up) |
| **vaastav/Fantasy-Premier-League** | Historical FPL per-Gameweek CSVs back to 2016-17, `merged_gw.csv`, FPL's own xP, Understat folders up to 2024-25 | 2026-27 reaches **GW6** (commit 2026-10-22) | Git / raw CSV | Code is MIT. README: "The data provided is property of [FPL] and [Understat]. I don't own any of the data" | GitHub raw limits | Weekly updates stopped. Now 3 major updates a season, though 26/27 has had a few extras | **Use for backtests only** |
| **FPL-Core-Insights** (`olbauday`, formerly FPL-Elo-Insights) | FPL snapshots per Gameweek, plus per-player match stats (xG, xA, xGOT, CBIT, duels, passes, distance), shots, xG by minute, momentum, cups and Europe | Commits several times daily. Latest 2026-11-19 16:43 UTC | Git / raw CSV | **No LICENSE file.** README: "Feel free to use the data ... in whatever way works best for you", with a link back requested. Upstream pipeline is private (Supabase) | GitHub raw limits | Active, one maintainer. 26/27 `elo` columns are empty | **Research only. Not a v1 dependency** |
| **FBref** | Basic stats only since January 2026. Advanced Opta data removed | Basic 26/27 rows exist **[Reported]** | Scraping only. Cloudflare challenge | Sports Reference bans tools built on scraped data and offers no API **[Reported]** | 20 requests a minute or a block of up to a day **[Reported]** | Advanced data has not come back, and no new provider is announced | **Avoid** |
| **Understat** | Team and player xG/xA/npxG, shots, top 6 leagues (EPL 2014/15 to 2026/27) | 26/27 page live on 2026-10-25 (Wayback) | Scraping internal AJAX/JSON. No official API | No terms, licence or permission found. Only a support email | Unknown | Format change in December 2025 broke the wrappers. Today it serves a maintenance page to generic clients | **Avoid** |
| **ClubElo** | Club Elo ratings and history | API down (502). Website still renders | Was a CSV API. Now reportedly needs auth | No terms or licence found | N/A | API effectively gone for anonymous use | **Avoid (for now)** |
| **football-data.org** | Fixtures, tables, delayed scores for 12 competitions including the PL | Live | REST, free key needs registration | Terms page not found (404). Policies page only covers throttling | Free: 10 requests a minute. Without a key: 100 a day | Commercial, long-running | **Skip**: duplicates the FPL API |
| **beyondELO** | Club Elo, rating deviation, home advantage, match ratings for European clubs | Unknown | REST/CSV, free key needs sign-in | **CC BY 4.0** (attribution required) | 10 a minute, 100 a day | New in 2026, operator not identified | **Watch** (possible ClubElo replacement) |
| **openfootball/football.json** | Fixtures and results JSON (has `2026-27/en.1.json`) | Last push 2026-09-22 | Git | **CC0** | GitHub limits | Volunteer project, irregular updates | Skip (the FPL API already has fixtures) |
| **FotMob** | Rich Opta-based match and player stats | Live | Internal API scraping | ToS (2026-10-22) forbid scraping, reproduction, redistribution and "systematic, regular, or bulk retrieval" without written consent | N/A | FotMob asked soccerdata to remove its scraper (January 2026) | **Avoid** |
| **premierleague.com** (and its pulselive feeds) | Official stats, lineups, news | Live | Scraping or undocumented API | T&Cs forbid "creating a database ... that includes material downloaded" without written approval, and any commercial use | N/A | Official | **Avoid as a data source** (news is ticket 10's question) |
| **API-Football** (api-sports) | Fixtures, lineups, stats, odds, predictions | Live | REST, key needs registration | Not checked (site returned 403) | Free: 100 requests a day **[Reported]**. Whether the current season is on the free plan is unclear | Commercial | Not evaluated. Low priority |

### Source notes

#### FPL API: already the richest free per-Footballer signal
- `bootstrap-static` (fetched 2026-11-19) lists 672 elements. Each has `expected_goals`, `expected_assists`, `expected_goal_involvements`, `expected_goals_conceded` (and per-90 versions), `defensive_contribution`, `clearances_blocks_interceptions`, `recoveries`, `tackles`, `starts`, `penalties_order`, `corners_and_indirect_freekicks_order`, `chance_of_playing_next_round` and `news` **[Verified]**. Source: https://fantasy.premierleague.com/api/bootstrap-static/
- vaastav's 2026-27 `merged_gw.csv` header shows the same xG and CBIT fields per Gameweek, along with FPL's own `xP` **[Verified]**. That confirms the per-Gameweek history endpoint carries them. Source: https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2026-27/gws
- Events: GW10 `is_current` and finished (deadline 2026-11-06), GW11 `is_next` (deadline 2026-11-21T11:00Z) **[Verified]**. The ticket's "roughly GW12" is one Gameweek ahead.

#### football-data.co.uk: free odds and match xG in one CSV
- The 2026/27 Premier League file `E0.csv` has 100 matches up to 2026-11-08. Its columns include `HxG`, `AxG`, shots, corners, cards, Bet365/Betfair/BetVictor/BetWay/Paddy Power/Sky Bet 1X2, closing (`C`) odds, over/under 2.5 and Asian handicap **[Verified]**. Source: https://football-data.co.uk/mmz4281/2627/E0.csv
- **Changed for 2026/27:** the 2024/25 and 2025/26 files had Pinnacle columns (`PSH`, `PSCH`) and no xG. The 2026/27 file adds `HxG`/`AxG` and drops the Pinnacle columns **[Verified]**. Sources: https://football-data.co.uk/mmz4281/2526/E0.csv, https://football-data.co.uk/mmz4281/2425/E0.csv
- Its notes credit XScores, the BBC, Flashscore, ESPN and others for statistics, and Betbrain, Oddsportal and individual bookmakers for odds. "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games." The notes don't name a source for the xG column **[Verified]**. Source: https://football-data.co.uk/notes.txt
- No licence or terms of use found. The disclaimer only covers accuracy and gambling liability **[Verified]**. Source: https://football-data.co.uk/disclaimer.php
- The match xG values are identical to FPL-Core-Insights' values for the same match (Man United v Aston Villa, 2026-11-08: 3.55 v 2.88) **[Verified]**. That suggests both share an upstream provider **[Inference]**.
- [Inference] Free to download, and widely used in academic and hobby work for two decades. The data has no explicit licence, so the bot should **download it at runtime and keep it, not commit or republish the CSVs in the repo**.

#### The Odds API
- Free "Starter" plan: "500 credits per month", "All sports", "Most bookmakers", "All betting markets". The API key arrives by email **[Verified]**. Source: https://the-odds-api.com/
- Cost: "1 per region per market" on `/odds`. `/events/{id}/odds` costs unique markets returned × regions. Historical endpoints cost 10× and are paid-only. `/sports` and `/events` are free **[Verified]**. Source: https://the-odds-api.com/liveapi/guides/v4/
- Soccer player props (`player_goal_scorer_anytime`, `player_shots_on_target`, `player_assists`, `player_to_receive_card` and others) exist for the EPL, but coverage is "currently limited to US bookmakers" **[Verified]**. Source: https://the-odds-api.com/sports-odds-data/betting-markets.html
- Terms (last updated 31 August 2026) allow "Displaying our data in a UI, website, or mobile app, including for commercial use", "Storing our data and retaining it indefinitely" and "Using our data to train statistical and machine learning models". They forbid reselling or redistributing the data "as a standalone data product". "Attribution ... is not required" **[Verified]**. Source: https://the-odds-api.com/terms-and-conditions.html
- [Inference] Budget: one h2h + totals pull for the UK region before each deadline costs 2 credits per call. That is about 80 credits a month even with daily pulls. Anytime-scorer props for 10 fixtures cost about 10 credits per Gameweek. 500 a month is plenty for a small group. Each self-hoster needs their own key, so it must stay optional and configured through an env var.

#### vaastav/Fantasy-Premier-League
- LICENSE is MIT (copyright 2017-19 Vaastav Anand). It adds: "The data provided is property of http://fantasy.premierleague.com and https://understat.com. I don't own any of the data" **[Verified]**. Source: https://github.com/vaastav/Fantasy-Premier-League/blob/master/LICENSE
- README: "weekly updates ... have been stopped at the end of the 2024-25 season". Since then there have been 3 major updates a season (start, end of January window, end of season) **[Verified]**. Source: https://github.com/vaastav/Fantasy-Premier-League
- 2026-27 so far: commits on 2026-08-04 (initial), 08-20, 08-28 (GW1) and 10-22 (GW6). `gws/` holds gw1 to gw6 plus some FPL `xP` files **[Verified]**. Source: https://github.com/vaastav/Fantasy-Premier-League/commits/master
- The `understat/` folder exists for 2024-25 but not for 2025-26 or 2026-27 **[Verified]**. Source: https://github.com/vaastav/Fantasy-Premier-League/tree/master/data
- A README caveat (commit #222, April 2026) warns that xP scraping timing can cause lookahead. That matters for backtests **[Verified, commit title only]**.

#### FPL-Core-Insights (formerly FPL-Elo-Insights)
- `olbauday/FPL-Elo-Insights` now redirects to `olbauday/FPL-Core-Insights`, "the data engine powering fplcore.com". The GitHub API reports no licence, and the repo has no LICENSE file **[Verified]**. Source: https://github.com/olbauday/FPL-Core-Insights
- README: "Feel free to use the data from this repository in whatever way works best for you ... include a link back". It says sources are the FPL API, "Manually Curated Match Stats (Opta-like)" and "ClubElo.com Elo Ratings". It claims refreshes twice daily. The workflow actually runs three times a day (07:30, 15:30, 23:30 UTC), exporting from a private Supabase pipeline **[Verified]**. Source: https://github.com/olbauday/FPL-Core-Insights/blob/main/.github/workflows/update_data.yml
- 2026/27 `teams.csv` has empty `elo` and `fotmob_name` columns. GW10 `matches.csv` has empty `home_team_elo` and `away_team_elo` but populated xG. GW10 `playermatchstats.csv` has 583 rows with xg, xa, xgot, tackles, interceptions, recoveries, blocks, clearances, `distance_covered` and `top_speed` **[Verified]**. Source: https://github.com/olbauday/FPL-Core-Insights/tree/main/data/2026-2027
- [Inference] The `fotmob_name` column, the momentum and xG-by-minute files, and the xGOT fields all match FotMob's data model. "Manually curated" is therefore probably FotMob-derived. FotMob's ToS forbid redistributing its data, so this repo's licensing rests on thin ground despite its permissive wording.

#### FBref
- On 20 January 2026, Sports Reference removed FBref's advanced data "effective immediately" after Opta/Stats Perform terminated its feeds and required deletion of the data. Basic stats remain **[Reported: Awful Announcing, 2026-01-23]**. Sources: https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html, https://www.theixsports.com/the-ix-soccer/fbrefs-loss-advanced-stats-womens-soccer-data-accessibility/
- No report of the data being restored or a new provider by 2026-11-19 **[Reported, absence of evidence]**. I could not read the Sports Reference blog because the site returned 403 / Cloudflare.
- fbref.com and sports-reference.com (including `robots.txt`, `bot-traffic.html` and `termsofuse.html`) return a Cloudflare "Just a moment..." challenge (HTTP 403) to a scripted client **[Verified]**. A community issue (2026-08-05) reports "CAPTCHA detected" in soccerdata's FBref scraper **[Verified issue exists]**. Source: https://github.com/probberechts/soccerdata/issues/967
- Sports Reference's policy pages, seen through search snippets only: a block for more than 20 requests a minute, jail for up to a day, no API "due to data licensing agreements", and a ban on creating websites or tools from scraped data and on generative-AI training without permission **[Reported]**. Sources: https://www.sports-reference.com/bot-traffic.html, https://www.sports-reference.com/data_use.html

#### Understat
- A Wayback snapshot from 2026-10-25 shows "EPL xG Table and Scorers for the 2026/2027 season", covering seasons 2014/15 to 2026/27 across 6 leagues. Its only footer contact is `support@understat.com`. There is no terms or licence link **[Verified]**. Source: http://web.archive.org/web/20261025161448/https://understat.com/league/EPL
- On 2026-11-19, every path on understat.com, including `robots.txt`, returned HTTP 200 with a "We will come back soon" page to my generic client **[Verified]**. It could be an outage or bot filtering, and I can't tell which **[Inference]**. I did not try to get around it.
- In December 2025 Understat moved to AJAX endpoints, which broke the HTML-parsing wrappers. understatAPI #15 and #16 were fixed in v0.7.0. amosbastian/understat #39/#40, plus #42 from 2026-07: "master branch is not working" **[Verified issues exist]**. Sources: https://github.com/collinb9/understatAPI/issues/15, https://github.com/amosbastian/understat/issues/42

#### ClubElo
- `http://api.clubelo.com/2026-11-19`, `/2026-11-01` and `/Arsenal` all return HTTP 502 with no body. `/Fixtures` returns `Fixtures API deactivated`. HTTPS times out. `clubelo.com/API` redirects to the homepage **[Verified]**.
- soccerdata issue #977 (2026-09-23) says the API "has moved behind authentication, and registration isn't open yet". The website still embeds recent ratings in vega-lite JSON **[Reported]**. Source: https://github.com/probberechts/soccerdata/issues/977
- [Inference] The bot doesn't need Elo. FPL's own team `strength_*` fields, together with odds, cover fixture difficulty.

#### football-data.org
- Free plan: 12 competitions including the Premier League and Championship, 10 calls a minute, delayed scores and schedules, tables. Lineups, scorers, bookings and squads need "Free + Deep Data" (€29). Odds and Stats add-ons are paid **[Verified]**. Sources: https://www.football-data.org/coverage, https://www.football-data.org/pricing
- "10 requests/minute in the free plan". Unauthenticated: "100 requests per 24 hours", limited to area and competition resources **[Verified]**. Source: https://docs.football-data.org/general/v4/policies.html
- I found no current terms of use: `/terms` returns 404 **[Verified]**.

#### Other sources found
- **beyondELO**: club Elo, rating deviation and home advantage. CC BY 4.0. A key is required (sign-in), 10 requests a minute and 100 a day. The operator is unnamed and the copyright says 2026 **[Verified from its developer page]**. Source: https://beyondelo.com/developers
- **FootInsights**: offers a pre-match 1X2/O-U probabilities CSV under CC BY 4.0, data since August 2026. It is self-promoted in a soccerdata issue and I have not vetted it **[Reported]**. Source: https://github.com/probberechts/soccerdata/issues/992
- **openfootball**: CC0 fixtures and results, `2026-27/en.1.json` present **[Verified]**. Source: https://github.com/openfootball/football.json
- **FotMob**: its ToS (dated 22 October 2026) say: "Use of the data ... including but not limited to scraping, reproduction, redistribution, or commercial purposes, without the express written consent of FotMob is strictly prohibited". They also forbid "systematic, regular, or bulk retrieval" **[Verified]**. FotMob formally asked soccerdata to remove its scraper **[Verified issue exists]**. Sources: https://www.fotmob.com/tos.txt, https://github.com/probberechts/soccerdata/issues/918
- **premierleague.com**: its T&Cs forbid reproducing, re-using or redistributing content and "creating a database ... that includes material downloaded" without prior written approval. They also forbid commercial use **[Verified via fetch]**. Source: https://www.premierleague.com/en/terms-and-conditions
- **API-Football**: free plan of 100 requests a day **[Reported]**. Whether it covers the current season is unclear, and its pricing page returned 403. Sources: https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide, https://www.api-football.com/pricing

## Implications for the bot's design

1. **Build the xP model on the FPL API alone.** Its per-Gameweek xG, xA, xGC, minutes, starts and defensive contribution cover attacking and defensive returns under the current scoring rules. That makes the bot legally simplest and gives it a single upstream.
2. **Use odds as the fixture-strength and team-goal signal.** Pull football-data.co.uk's CSV once per Gameweek (after Friday or Tuesday odds collection) for historical closing odds and match xG. Optionally call The Odds API before each deadline for upcoming h2h and totals. Implied team goals and clean-sheet probabilities follow from these.
3. **Never commit third-party data to the public repo.** Fetch it at runtime into a local cache. The repo should contain only code, plus attribution in the README. Even "permissive" community datasets (vaastav, FPL-Core-Insights) say the data isn't theirs or have no licence.
4. **Keep sources pluggable behind one ingestion seam (ticket 13).** In 2026, three of the ten candidates broke or changed terms (FBref, ClubElo, Understat). Each adapter should fail soft: xP falls back to the FPL API alone.
5. **The Odds API is opt-in.** It needs a per-deployment key from an email sign-up, so it stays an env-var-gated adapter and can't be a hard requirement for a self-hoster.
6. **Backtesting:** use vaastav history (2016-17 onwards) for model calibration. Mind its documented xP lookahead caveat, and don't redistribute derived datasets.
7. Don't scrape premierleague.com, FotMob, Sofascore, WhoScored or FBref for stats. Team news for Scout mode is a separate question (ticket 10).

## Open questions

- **FPL's own terms** on automated reads of `/api/` and on displaying the data in a public open-source tool. The `/help/terms` page is a JavaScript app, so I couldn't read it here. That is ticket 01's question.
- **football-data.co.uk's xG source** and whether that source imposes conditions. It isn't named in `notes.txt`. Worth an email to the site owner before relying heavily on the xG column.
- **Understat**: is today's "come back soon" page a temporary outage or a block on non-browser clients? Recheck in a week. Even if it comes back, it has no terms, so it stays on the avoid list.
- **ClubElo**: will the authenticated API open for registration, and on what terms? beyondELO could replace it if Elo ever becomes useful, but its operator is unidentified.
- **The Odds API free plan**: which UK bookmakers count as "most bookmakers" for `soccer_epl`, and do any free-plan bookmakers carry EPL player props? US-only coverage suggests the props are thin. Check with a real key.
- Whether FBref gets advanced data back from a new provider during 2026/27. Low priority, since the FPL API covers the need.

## Sources

- FPL API bootstrap-static: https://fantasy.premierleague.com/api/bootstrap-static/
- football-data.co.uk: https://football-data.co.uk/mmz4281/2627/E0.csv, https://football-data.co.uk/mmz4281/2526/E0.csv, https://football-data.co.uk/mmz4281/2425/E0.csv, https://football-data.co.uk/notes.txt, https://football-data.co.uk/disclaimer.php
- The Odds API: https://the-odds-api.com/, https://the-odds-api.com/liveapi/guides/v4/, https://the-odds-api.com/sports-odds-data/betting-markets.html, https://the-odds-api.com/terms-and-conditions.html
- vaastav: https://github.com/vaastav/Fantasy-Premier-League, https://github.com/vaastav/Fantasy-Premier-League/blob/master/LICENSE, https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2026-27
- FPL-Core-Insights: https://github.com/olbauday/FPL-Core-Insights, https://github.com/olbauday/FPL-Core-Insights/blob/main/.github/workflows/update_data.yml, https://github.com/olbauday/FPL-Core-Insights/tree/main/data/2026-2027
- FBref / Sports Reference: https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html, https://www.theixsports.com/the-ix-soccer/fbrefs-loss-advanced-stats-womens-soccer-data-accessibility/, https://www.sports-reference.com/bot-traffic.html, https://www.sports-reference.com/data_use.html, https://github.com/probberechts/soccerdata/issues/967
- Understat: http://web.archive.org/web/20261025161448/https://understat.com/league/EPL, https://github.com/collinb9/understatAPI/issues/15, https://github.com/amosbastian/understat/issues/42
- ClubElo: http://api.clubelo.com/Fixtures, https://github.com/probberechts/soccerdata/issues/977
- football-data.org: https://www.football-data.org/coverage, https://www.football-data.org/pricing, https://docs.football-data.org/general/v4/policies.html
- beyondELO: https://beyondelo.com/developers
- FootInsights: https://github.com/probberechts/soccerdata/issues/992
- openfootball: https://github.com/openfootball/football.json
- FotMob: https://www.fotmob.com/tos.txt, https://github.com/probberechts/soccerdata/issues/918
- Premier League T&Cs: https://www.premierleague.com/en/terms-and-conditions
- API-Football: https://www.api-football.com/pricing, https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide
