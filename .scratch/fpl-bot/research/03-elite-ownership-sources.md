# Where to get Elite ownership (top 1k / 10k / 100k)

Research for ticket `issues/03-elite-ownership-sources.md`. Researched 2026-11-19. The ticket assumed roughly Gameweek 12, but the official API reports Gameweek 10 as current and finished, with the Gameweek 11 deadline at 2026-11-21 11:00 UTC ([bootstrap-static][bs]).

Labels used below:
- **[verified]**: I checked it directly against the primary source (an HTTP response, a JSON file, a terms text).
- **[community]**: what third-party write-ups or common FPL-developer knowledge say. I did not verify it.
- **[inference]**: my own reasoning from verified facts.

## TL;DR

- **The official API has no cohort figures.** It gives only overall-game numbers: `selected_by_percent` per Footballer, `most_captained`, and `chip_plays` counts across all ~11.3M managers. There is nothing for a top 10k or top 100k. [verified, [bs]]
- **LiveFPL is the only free source I found that publishes Elite ownership in machine-readable form.** Its site loads public JSON files from `livefpl.us`:
  - `top10k.json`: effective ownership (EO) per Footballer across the full top 10k.
  - `elite.json`: the same for its own "Elite" list of 1,000 managers.
  - `locals_{gw}.json`: captaincy, triple-captain and chip usage for Top 100, Top 1K and Top 10K (all full counts), plus Top 100K (**a 1,000-manager sample**) and deeper rank bands.

  All of these refreshed today. [verified, [lf-js], [lf-top10k], [lf-locals]]
- **LiveFPL publishes no terms of use and no API, and none of its data is licensed.** `livefpl.us/robots.txt` allows all crawlers. The JSON files are undocumented internal endpoints of an ad-funded site, so the format can change without notice and reuse has no permission behind it. Treat LiveFPL as a cross-check, or ask its author first. It is not a dependency. [verified for robots and missing ToS; the rest is inference]
- **Fantasy Football Hub's ToS explicitly forbid scraping, "including extracting data for personal use"** (cl. 6.6.2). Not usable. [verified, [ffh-terms]]
- **Fantasy Football Fix keeps its tiered ownership and EO behind Premium.** Its ToS (s.11) say all its data and statistics are its IP and may not be reproduced without permission. Not usable. [verified, [fff-terms], [fff-features]]
- **FPL Review publishes an "Elite 1000"**: a fixed set of 1,000 managers chosen before the season, covering ownership, EO, captaincy and chips. That is not the top 10k or 100k. It has no API, and data export is a Patreon feature. Not usable. [verified, [fplr-elite], [fplr-premium]]
- **FPL Statistics could not be reached.** Its TLS certificate is for a different host. No GitHub dataset I found has cohort ownership either: vaastav's dataset is per-Footballer only. [verified, [fplstat], [vaastav]]
- **Recommendation: build our own sampler on the official API.** The official API is the only source whose cohort definition matches the GLOSSARY (rank in the overall top 10k or top 100k at a given Gameweek). It also gives chips and captaincy for free, and it puts us on the same legal footing as the rest of the bot. For a worst-case ±2% margin at 95% confidence, it needs about **1,940 managers for the top 10k and about 2,350 for the top 100k**. With a stratified design, that is about **4,400 requests per Gameweek, or 25 minutes at 3 req/s**. [verified statistics; plan is inference]
- **Legal caveat for every option that reads FPL data:** the 2026/27 FPL Terms, cl. 28(d), say users shall not "use automated systems to access the Game and extract information from the Game". Cl. 29 says the Premier League owns "any Game data". The whole FPL tool ecosystem, LiveFPL included, depends on that same data, and the bot already depends on the API for everything else. So this is a project-wide risk, not a reason to prefer one source over another. Keep volume low, cache, stay non-commercial and give attribution. [clauses verified, [fpl-terms]; risk assessment is inference, not legal advice]
- **Picks for the upcoming Gameweek are not visible before its deadline.** The endpoint returns 404 "Not found." So any Elite ownership is as of the *last* deadline. Pre-deadline figures, such as LiveFPL's `predictedEOs`, are models, not observations. [verified, [picks]]

## Detailed findings

### 1. Official FPL API

**What exists** [verified, [bs]]
- `bootstrap-static` reports `total_players: 11,303,484`.
- Per Footballer it gives `selected_by_percent`, which is overall ownership.
- Per event it gives `most_selected`, `most_captained`, `most_vice_captained` and `chip_plays`. Example for GW10: Bench Boost 282,173, Free Hit 80,369, Wildcard 136,671, Triple Captain 133,007.
- All of these cover the whole game. There is no top-N breakdown.

**Building blocks for our own sampler** [verified]

- **Overall league standings:** `GET /api/leagues-classic/314/standings/?page_standings={p}` ([st1], [st2000]).
  - League 314 is named "Overall".
  - 50 entries per page. Fields: `entry`, `rank`, `rank_sort`, `total`, `event_total`, `last_rank`, `entry_name`, `player_name`.
  - Page 1 covers ranks 1–50. Page 2000 ends at `rank_sort` 100000.
  - **Ties:** on page 2000 every row has `rank` 99,036, but `rank_sort` runs from 99,951 to 100,000. Use `rank_sort` to draw cohort boundaries.
  - Response headers: `cache-control: no-store` and `x-cache: MISS`, so every standings call reaches the origin. `last_updated_data` was a few minutes old.
- **Squad picks:** `GET /api/entry/{entry_id}/event/{gw}/picks/` ([picks]).
  - Fields: `active_chip`, `automatic_subs`, `entry_history` (including `overall_rank`), and `picks[]` (`element`, `position`, `multiplier`, `is_captain`, `is_vice_captain`).
  - That covers ownership, captaincy and chips in one call. One call is about 1.9 KB.
  - **Caching:** for a finished GW the response came from the CDN (`x-cache: HIT`, `age: 231846`, `edge-control: max-age=1209600`). Picks for a locked Gameweek are therefore cached at the edge for up to 14 days.
  - **Upcoming GW:** `/event/11/picks/` (deadline not yet passed) returned **404 `{"detail":"Not found."}`**.
- **No auth needed:** none of the GET endpoints above required login.
- **robots.txt:** `fantasy.premierleague.com/robots.txt` returns the single-page-app HTML, not a robots file. So there is no robots policy either way ([robots]).

**Terms of use** [verified, [fpl-terms]]

The terms are rendered client-side; the text comes from the site's `Terms-*.js` bundle.
- **Title:** "2026/27 Fantasy Premier League – Terms & Conditions".
- **Who is bound:** the preamble defines "you" as "any user of this website whatsoever".
- **Cl. 28:** "You also warrant and agree that you shall not: … (b) … exploit any information or other material obtained through the Game for commercial purposes … (c) engage in spamming or flooding; (d) use automated systems to access the Game and extract information from the Game".
- **Cl. 29:** "The Premier League is the owner of all intellectual property rights in the Game, including … any Game data. Such rights must not be used by any Player in any way without the prior written consent of the Premier League."

**Rate limits**
- No rate limit is published anywhere I could find. [verified absence for the official site; search turned up nothing]
- [community] Developers commonly report throttling (429 or 403) under high concurrency. I found no authoritative figure.
- [inference] Plan for 2–3 req/s with exponential backoff that honours `Retry-After`.

### 2. LiveFPL (livefpl.net)

**Access method** [verified, [lf-js]]
- The site is a single-page app. Its bundle `main-BgOy4Kip.js` reads static JSON from `https://livefpl.us`:
  - `top10k.json`
  - `elite.json`
  - `locals_${gw}.json`
  - `predictedEOs/${gw}.json`
  - `players.json`, `teams.json`, `types.json`, `prediction.json`, `top_transfers.json`
- It also calls a Cloud Run API (`livefpl-api-…run.app/LH_api2/…`) and `www.livefpl.net/livefplapi/…`.
- None of this is documented as a public API.

**What the files contain**

- **`top10k.json`** [verified, [lf-top10k]]
  - Map of `element_id` to a value. Example: Haaland 1.756, Raya 0.655.
  - The values sum to about 12.1. [inference] That is 11 starters plus the captain bonus, so the value is **effective ownership** (starting XI weighted by multiplier), not raw 15-man ownership.
  - Last-Modified: 2026-11-19 16:35 GMT.
- **`elite.json`** [verified, [lf-elite]]
  - Same shape, for LiveFPL's "Elite" cohort of 1,000 managers.
  - [community] It is LiveFPL's own curated list of historically strong managers. I did not find its selection method.
- **`locals_10.json`** [verified, [lf-locals]] (Last-Modified 2026-11-19 16:52 GMT)
  - Holds the cohorts in the table below. Each has:
    - `chip_percent` for this GW and for the season so far
    - `hits_mean`
    - `captains`: a list of `[element, share]`
    - `triple_captains`
  - Per-Footballer ownership is **not** in this file. Per-tier ownership exists only for the top 10k and Elite (the files above).
- **`predictedEOs/11.json`** [verified, [lf-pred]]
  - Pre-deadline *predicted* EO for the next GW. It is a model, not observed picks.

| LiveFPL cohort | Label in JSON | Size used |
|---|---|---|
| Top 100, Top 1K, Top 10K | `top10k` (full count) | 100 / 1,000 / 10,000 |
| Top 100K | `sample` | **1,000** |
| 100K–200K … 900K–1M | `sample` | 1,000 each |
| 1M–1.5M, 1.5M–2M | `sample` | 5,000 each |
| 2M–3M, 3M–6M | `sample` | 10,000 / 30,000 |
| Top 1M | `mixed` | 19,900 |
| Elite | `elite` | 1,000 |
| Overall | `overall` | 112,500 |

[inference] LiveFPL's top-100k captaincy figures rest on n=1,000. That gives a worst-case margin of about ±3.1% at 95% confidence (see §7). It is fine for a headline, but coarser than the ticket's 1–2% target.

**Update frequency**
- [verified] `top10k.json` and `elite.json` were modified today at 16:35. `locals_10` was modified at 16:52. All are served with `cache-control: max-age=0` (or 60 s).
- [inference] They update several times a day. LiveFPL is a live-rank site, so updates are probably most frequent during a Gameweek.

**ToS position**
- [verified] `www.livefpl.net/robots.txt` returns 404 (no file). `livefpl.us/robots.txt` says `User-agent: * Allow: /` ([lf-robots]).
- [verified] The app's routes include no terms or legal page ([lf-js]), and a web search found no LiveFPL terms.
- [verified] The site is ad-funded: it loads pub.network ad scripts and has a `/remove_ads` route.
- [inference] There is no licence, so default copyright (and in the UK and EU, database right) applies. Pulling the JSON is technically trivial, but it is unpermissioned reuse of an independent developer's work. Its upstream data also falls under FPL cl. 28–29.

### 3. Fantasy Football Fix

- **Cohorts and features** [verified, [fff-features]]
  - "Insight Live" lets you compare ownership and EO across rank tiers.
  - "Pre-deadline Captain Reveal" shows projected captaincy and EO, filterable by rank.
  - Its blog runs articles on top-100k ownership, with the tables behind Premium ([fff-100k], read via search snippet).
  - [verified] The features page names no exact tiers, no prices, and no API or export.
- **ToS** [verified, [fff-terms]]
  - Section 11 says "All information, data, and statistics published by Fix Sports Stats Ltd" are its IP and "may not be reproduced, used or represented without the express permission".
  - The ToS have no explicit scraping clause.
- **Verdict:** not usable without a licence.

### 4. Fantasy Football Hub (FFHub)

- **Cohorts:** I found no top-10k or Elite ownership tool in its terms or in search results. [verified absence in [ffh-terms]; search only]
- **ToS** [verified, [ffh-terms]]
  - Cl. 6.6.1 prohibits "automated access methods such as bots, scripts…designed to extract data".
  - Cl. 6.6.2 prohibits "data scraping, crawling… This includes extracting data for personal use".
  - Cl. 6.6.3 forbids using its data to train or improve "machine learning models, AI systems".
- **Verdict:** not usable.

### 5. FPL Review

- **Cohorts** [verified, [fplr-elite]]
  - The "Elite 1000" is "a sample of 1,000 FPL managers pre-selected before each season kicks off", fixed at the season's start.
  - It shows ownership, EO, captaincy and chip usage. That is a different cohort from the GLOSSARY's top 10k or top 100k.
- **Free or Premium:** the premium page does not list Elite data. Free or paid is **unverified**. [verified, [fplr-premium]]
- **Access:** "Data Export" is a Patreon perk ([fplr-premium]). There is no API. The site is a JS app.
- **robots.txt** [verified, [fplr-robots]]
  - Sets `Content-Signal: search=yes, ai-train=no, use=reference`.
  - Says nothing about `ai-input`, which the file itself says means "neither grants nor restricts".
- **Published ToS:** none found.
- **Verdict:** not usable.

### 6. Others

- **FPL Statistics (fplstatistics.co.uk):** HTTPS failed. The certificate presented is for a different host ([fplstat]).
  - I could not verify what it publishes.
  - [community] It is mainly known as a price-change predictor.
- **Fantasy Football Scout:** publishes top-10k ownership and chip *articles*, built on LiveFPL data ([ffs-art]). These are prose, not data. [community]
- **vaastav/Fantasy-Premier-League (GitHub):** the 2026-27 folder holds `players_raw.csv`, `gws/gw1..6.csv`, `merged_gw.csv` and `xP*.csv` ([vaastav]). That is per-Footballer data with no cohort ownership. [verified]
- **Other GitHub searches:** "fpl top10k" and related searches found only `UnfairWaffles/fpl_top10k`, a 3-day-old app with no licence and no dataset. It calls the same standings and picks endpoints ([waffles]). [verified]
- **Conclusion:** I found no maintained community dataset of top-N ownership.

### 7. Fallback design: sample Squads from the official API

**Estimand (per cohort C, Gameweek g)** [inference; definitions match the GLOSSARY]
- **Cohort:** managers with `rank_sort` ≤ 10,000 (or ≤ 100,000) in league 314, read after the GW g deadline.
  - At that point standings reflect totals through GW g−1. So the cohort is "ranked in the top N going into GW g".
- **Ownership** of Footballer f: the share of sampled Squads with f in `picks` (all 15).
  - Optionally also XI ownership: `multiplier > 0`.
- **Captaincy:** the share with `is_captain` on f. Track triple captain separately via `active_chip == "3xc"`.
- **EO:** mean `multiplier` across the sample. This is comparable to LiveFPL's `top10k.json`.
- **Chip usage:** the distribution of `active_chip`.

**Sample size for a proportion at 95% confidence, worst case p = 0.5, with finite-population correction** [verified arithmetic]

The formula: n₀ = 1.96²·p(1−p)/E², and n = n₀ / (1 + (n₀−1)/N).

| Cohort (N) | ±3% | ±2% | ±1.5% | ±1% |
|---|---|---|---|---|
| Top 1k (1,000) | 517 | 707 | 811 | 906 → just take all 1,000 |
| Top 10k (10,000) | 965 | **1,937** | 2,992 | **4,900** |
| Top 100k (100,000) | 1,056 | **2,345** | 4,094 | **8,763** |

Margin of error at fixed sample sizes:

| n | Top 10k (p = 0.5) | Top 100k (p = 0.5) | Top 100k (p = 0.1) |
|---|---|---|---|
| 1,000 (LiveFPL's top-100k size) | ±2.9% | **±3.1%** | ±1.9% |
| 2,000 | ±2.0% | ±2.2% | ±1.3% |
| 2,500 | ±1.7% | ±1.9% | ±1.2% |
| 5,000 | ±1.0% | ±1.35% | ±0.8% |

The worst case applies only to Footballers owned by about 50%. Low-owned differentials (around 10%) and dominant captains (around 80%) come out tighter.

**Recommended design (±2% on both cohorts), stratified** [inference]

1. **Stratum A, ranks 1–10,000.** Fetch all 200 standings pages. That gives a full ID list, cheap at ~11 KB each. Draw a simple random sample of 1,940 entries. Their mean gives the **top-10k** estimate directly.
2. **Stratum B, ranks 10,001–100,000.** Draw 250 random pages from pages 201–2000 and take 8 random entries from each, which is 2,000 entries.
   - [inference] Taking 8 per page keeps the cluster design effect to about 1 + 7ρ. That is about 1.07 if neighbours in rank are only weakly correlated (ρ ≈ 0.01).
   - The **top-100k** estimate is 0.1·p̂_A + 0.9·p̂_B. With these sizes it lands at about ±2%.
3. **Request count:** 200 + 250 standings, plus about 3,940 picks, which is **about 4,400 requests per GW**.
   - Compare: two independent samples would need 4,282 picks plus up to 2,000 standings pages. A plain random sample of 2,345 entries from the top 100k touches about 1,380 distinct pages.

**Options and cost**

| Plan | Standings calls | Picks calls | Total | @1 req/s | @3 req/s | @5 req/s |
|---|---|---|---|---|---|---|
| **±2% stratified (recommended)** | 450 | ~3,940 | ~4,400 | 73 min | **24 min** | 15 min |
| ±1% stratified (10k: 4,900; 100k-B: ~8,000 over ~1,000 pages × 8) | ~1,200 | ~12,900 | ~14,100 | 3.9 h | 78 min | 47 min |
| Full census of top 10k + ±2% top 100k | 450 | ~12,000 | ~12,450 | 3.5 h | 69 min | 42 min |
| Top-1k census only (add-on) | 20 | 1,000 | 1,020 | 17 min | 6 min | 3.4 min |

Bandwidth is trivial: about 4,400 × 2–11 KB, roughly 15 MB per GW.

**Timing and load** [inference]
- Run once per GW, after the deadline, once FPL's post-deadline "game is updating" lock clears. [community] That lock typically lasts under an hour.
- Picks endpoints for a locked GW are CDN-cached for 14 days. Repeat runs and other tools' traffic will mostly hit the edge, not the origin. Standings are not cached, so keep standings calls to the minimum above.
- Run sequentially, or at concurrency 2–3, with jitter and backoff on 429 or 403, and a generic User-Agent.
- Persist the raw picks so a rerun never re-fetches them.

## Implications for the bot's design

- **The sampler belongs in the data ingestion layer** (ticket 13): one post-deadline job per GW that writes `elite_ownership(gw, cohort, element, own_pct, xi_pct, cap_pct, eo, n, moe)` plus a `chip_usage(gw, cohort, chip, pct)` table. Advice code then reads only these tables.
- **Store `n` and margin of error with every figure,** so Elite gap explanations can say "about 62% (±2%) of the top 10k".
- **Elite ownership is always as of the last deadline.** If the bot needs pre-deadline Elite trends, it must use transfers since then, or a model. That would be a separate feature; see the `predictedEOs` approach.
- **Keep the cohort definition exact:** `rank_sort` ≤ N in league 314 after the deadline. Our numbers will not exactly match LiveFPL's, which also uses a 1,000 sample for the top 100k.
- **Optional cross-check:** comparing our top-10k EO to LiveFPL's `top10k.json` is a cheap sanity check while developing. Do it only manually, or with the author's permission. Do not ship it as a runtime dependency.
- **The FPL Terms cl. 28(d) risk applies to the whole bot.** Record the stance in the security and open-source hygiene ticket (16): low volume, caching, no login, non-commercial, attribution, and a kill switch.

## Open questions

1. **LiveFPL permission:** would its author allow us to read `top10k.json` and `locals_*.json`? That would make the top-10k figures free and exact. It needs a human to ask; I sent nothing.
2. **Real FPL API throttling:** what threshold triggers 429 or 403 today, and does it differ for standings versus picks? Only safe empirical testing can answer this, with a gradual ramp from 1 req/s on a non-deadline day.
3. **Standings during a live GW:** are overall-league standings stable during the window after the deadline but before the GW is scored, when the sampler runs? Do they move during live matches? (`last_updated_data` was minutes old, and the response is assembled live from "rt" fields per the `x-ism-edge-rt-fields` header.)
4. **Ownership definition:** for Gaps, should Elite ownership mean 15-man ownership, XI ownership, or EO? The sampler can give all three. The GLOSSARY says ownership plus captaincy, which suggests 15-man ownership plus a captain share, with EO kept for the effective-ownership calculation.
5. **FPL Statistics:** its site was unreachable. Recheck later if a third source is wanted.
6. **FPL Review Elite data:** is it free? This only matters if an "Elite 1000"-style cohort is ever wanted. The GLOSSARY does not define one.

## Sources

[bs]: https://fantasy.premierleague.com/api/bootstrap-static/
[st1]: https://fantasy.premierleague.com/api/leagues-classic/314/standings/?page_standings=1
[st2000]: https://fantasy.premierleague.com/api/leagues-classic/314/standings/?page_standings=2000
[picks]: https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/
[robots]: https://fantasy.premierleague.com/robots.txt
[fpl-terms]: https://fantasy.premierleague.com/help/terms
[lf-js]: https://www.livefpl.net/assets/main-BgOy4Kip.js
[lf-top10k]: https://livefpl.us/top10k.json
[lf-elite]: https://livefpl.us/elite.json
[lf-locals]: https://livefpl.us/locals_10.json
[lf-pred]: https://livefpl.us/predictedEOs/11.json
[lf-robots]: https://livefpl.us/robots.txt
[fff-features]: https://www.fantasyfootballfix.com/web_features
[fff-terms]: https://www.fantasyfootballfix.com/terms/
[fff-100k]: https://www.fantasyfootballfix.com/blog-index/fpl-top-100k-most-owned-players-gameweek-1/
[ffh-terms]: https://www.fantasyfootballhub.co.uk/terms-and-conditions
[fplr-elite]: https://docs.fplreview.com/team-analysis/elite-1000/
[fplr-premium]: https://docs.fplreview.com/getting-started/premium-features
[fplr-robots]: https://fplreview.com/robots.txt
[fplstat]: https://www.fplstatistics.co.uk/
[ffs-art]: https://www.fantasyfootballscout.co.uk/2022/04/16/fpl-top-10k-chip-usage-and-players-owned-for-double-gameweek-33
[vaastav]: https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2026-27
[waffles]: https://github.com/UnfairWaffles/fpl_top10k

- Official FPL API, fetched 2026-11-19 with a generic User-Agent; seven requests in total:
  - bootstrap-static: https://fantasy.premierleague.com/api/bootstrap-static/
  - Overall league standings, pages 1 and 2000: https://fantasy.premierleague.com/api/leagues-classic/314/standings/?page_standings=1 and `…=2000`
  - Picks for GW10 and GW11 (a single public entry): https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/
  - robots.txt: https://fantasy.premierleague.com/robots.txt
- FPL 2026/27 Terms & Conditions: https://fantasy.premierleague.com/help/terms. The text was read from the page's bundle `https://fantasy.premierleague.com/assets/Terms-DUOzP1QV.js`.
- LiveFPL:
  - Bundle: https://www.livefpl.net/assets/main-BgOy4Kip.js
  - Data files: https://livefpl.us/top10k.json, https://livefpl.us/elite.json, https://livefpl.us/locals_10.json, https://livefpl.us/predictedEOs/11.json
  - robots.txt: https://livefpl.us/robots.txt; https://www.livefpl.net/robots.txt returns 404
- Fantasy Football Fix:
  - https://www.fantasyfootballfix.com/web_features
  - https://www.fantasyfootballfix.com/terms/
  - https://www.fantasyfootballfix.com/blog-index/fpl-top-100k-most-owned-players-gameweek-1/ (read via a search snippet only)
- Fantasy Football Hub: https://www.fantasyfootballhub.co.uk/terms-and-conditions and https://www.fantasyfootballhub.co.uk/robots.txt
- FPL Review:
  - https://docs.fplreview.com/team-analysis/elite-1000/
  - https://docs.fplreview.com/getting-started/premium-features
  - https://docs.fplreview.com/getting-started/faq/
  - https://fplreview.com/robots.txt
- FPL Statistics: https://www.fplstatistics.co.uk/ (TLS certificate mismatch on 2026-11-19)
- Fantasy Football Scout, community, from 2022: https://www.fantasyfootballscout.co.uk/2022/04/16/fpl-top-10k-chip-usage-and-players-owned-for-double-gameweek-33
- GitHub:
  - https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2026-27
  - https://github.com/UnfairWaffles/fpl_top10k
