# How FPL Price changes work in 2026/27, and how to predict them

Ticket: [04 – How FPL price changes work and how to predict them](../issues/04-price-change-mechanics.md)
Researched: 2026-11-19, between Gameweek 10 and 11 (GW10 deadline 2026-11-06; GW11 deadline 2026-11-21 11:00 UTC, so this is the international break).

Evidence labels used throughout:
- **[OFFICIAL]**: stated by FPL or the Premier League: the game's help/rules text, premierleague.com articles, or fields the official API returns.
- **[COMMUNITY]**: reverse-engineered or folk knowledge from third-party sites. Not confirmed.
- **[INFERENCE]**: my own analysis, mostly of a live official API snapshot taken on 2026-11-19 around 17:05–17:50 UTC. These are hypotheses to validate, not facts.

---

## TL;DR

1. **The big 2026/27 change: FPL now publishes its own Price change predictor, and the public API exposes it.** [OFFICIAL] Every Footballer in `/api/bootstrap-static/` now has `price_change_percent` (current progress), `price_change_hourly_rate`, `price_change_projections` (projected % and a likelihood code −5…+5 for each of the next 3 price deadlines), `price_change_locked_until` and `price_change_calibrating`. `game_config.settings.price_change_deadlines` lists the next deadlines, and `game_config.status.price_change_last_updated` timestamps each refresh. The data refreshes every 15 minutes. No login is needed.
2. **There is also an official history endpoint**, `/api/stats/price-changes/`. [OFFICIAL] It returns `{element, team, event, changed_at, cost_before, cost_after}` for recent changes. It is a rolling window: on 2026-11-19 it held 338 changes going back to 2026-10-08, so we must archive it daily ourselves.
3. **Timing: once a day at 00:00 UK time** (23:00 UTC during BST, 00:00 UTC during GMT). This replaces the old ~01:30 GMT / 02:30 BST run. [OFFICIAL] Changes are £0.1m per day at most. The premierleague.com article says a price "can rise or fall by up to £0.3m in a Gameweek". The rules page says only that prices move with "popularity … in the transfer market". FPL states that the formula "won't be revealed".
4. **Mechanics confirmed or strongly supported by the official numbers:**
   - Progress accumulates across days and resets to about 0 after a change. [OFFICIAL data / INFERENCE]
   - The rise threshold looks flat, about 130k "units" for everyone (≈1.15% of the 11.3M managers), whatever the ownership. After one rise in the same Gameweek it jumps about 2.7×, to ≈352k. [INFERENCE]
   - The fall threshold looks proportional to ownership, ≈11% of current owners. It is multiplied by ≈1.7 after a fall in the same Gameweek, ≈1.85 for doubtful (`d`) Footballers and ≈2.8 for injured or suspended (`i`/`s`) ones. [INFERENCE]
   - This matches the decade-old community theory: rise threshold ∝ active managers, fall threshold ∝ ownership, flagged Footballers fall more slowly. [COMMUNITY]
5. **Protection:**
   - Newly added Footballers are locked. `price_change_locked_until` is set and the UI shows "Unlocks in N days". [OFFICIAL]
   - I found no multi-day protection after a normal change. Footballers have changed on consecutive nights across a Gameweek boundary, and three times within one Gameweek. [OFFICIAL data]
   - Status-change resets (for example a flag cleared) are [COMMUNITY] lore that I could not verify.
6. **Wildcard and Free Hit transfers being excluded from price calculations is not stated anywhere official.** The official text excludes them only from transfer-count tie-breakers. The price claim is [COMMUNITY] (FFS 2015 and 2026 articles). The official progress already reflects whatever FPL counts, so the bot doesn't need to model it.
7. **Free predictors:** LiveFPL, FPL Statistics, Fantasy Football Hub (mostly behind membership), Fantasy Football Fix (paid), OneFPL and others. None publishes a reuse licence or a methodology. OneFPL's terms forbid scraping. **Don't reuse their data. Use the official fields.**
8. **Recommended design:** treat FPL's own `price_change_projections[0].likelihood` as the primary signal for the Price alert (±5 = "Very likely", ±4 = "Likely"). Snapshot `bootstrap-static` a few times each evening (ideally at 15-minute cadence from about 20:00 to 23:45 UK) and archive `/stats/price-changes/` daily. Score the official predictor's accuracy ourselves. A home-grown "shadow" predictor (sketched below) is a fallback in case FPL withdraws the fields, not a launch requirement.
9. **Realistic accuracy:** no trustworthy published accuracy figures exist. The last measured claim is Fix's "around 80%" from 2014. FPL itself warns that late transfers can push a Footballer back below 100% in the last 15 minutes. Expect very high precision for "Very likely" calls made after about 23:00 UK, and noticeably worse precision for calls made earlier in the evening. We should measure this rather than assume it.

---

## 1. Official facts

### 1.1 Rules and help text (fantasy.premierleague.com, 2026/27)

The game's help and rules strings ship in the site's public JS bundle (`/assets/index-*.js`, fetched 2026-11-19). Relevant entries:

- **Rules → Player Prices:** "Player prices change during the season dependent on the popularity of the player in the transfer market. Player prices do not change until the season starts." It adds the selling rule: you keep half of a rise, rounded down to £0.1m. For example, bought at £7.5m and now £7.8m gives a selling price of £7.6m. `game_settings.transfers_sell_on_fee = 0.5`.
- **FAQ "How do player prices change?":** prices "may change by £0.1m a day" and "can change at midnight UK time each day"; whether they do "depends on activity in the transfer market". The formula "include[s] variable factors and won't be revealed".
  - Status messages say "likely" or "very likely".
  - Early in the season the status is based on current progress. It switches to a prediction "once a suitable calibration period using live data is complete".
- **FAQ "The game said that my player would change … and they didn't":** "current progress and predicted progress do not guarantee a player's price will change."
- **FAQ "How do price changes affect the Free Hit chip?":** after a Free Hit, squad and bank are restored "with any player price changes in the previous gameweek reflected", and any change to the bank while the Free Hit was active is lost.
- **2026/27 Game Updates → Price Change Prediction:** "the daily price change deadline has been set at midnight UK time." It describes the new Price Changes page (progress %, then predicted progress after calibration, sorting, and filters for your team, watchlist or all players).
- **Price Changes page help sheet:** "When Predicted Progress exceeds 100%, the player is considered Very Likely to rise or fall." The page has a "(Updates every 15 minutes)" note, a countdown to the next deadline, and a "Recent Price Changes" history tab.
- **Wildcard and Free Hit:** the only official "will not count towards the total number of transfers" sentence sits under the **league tie-breaker** FAQ, not under prices.

Source: https://fantasy.premierleague.com/ (SPA; the strings are in the `/assets/index-DZSbhisR.js` bundle as of 2026-11-19). The human-readable pages are https://fantasy.premierleague.com/help/rules, https://fantasy.premierleague.com/help/new and https://fantasy.premierleague.com/price-changes.

### 1.2 premierleague.com articles

- "What's new in 2026/27 Fantasy: Price Change Predictor" (18 Oct 2026):
  - The predictor "uses official FPL data to track the transfer activity for every player".
  - Changes happen at 00:00 UK and the data refreshes every 15 minutes.
  - Over 100% means expected to pass the threshold.
  - A player "can rise or fall by up to £0.3m in a Gameweek".
  - It gives an example: at 105% at 23:45 a player can still fall back below the threshold.
  - Predicted progress appears "After a period of calibration of at least one Gameweek".
  - https://www.premierleague.com/en/news/4680462/whats-new-in-202627-fantasy-price-change-predictor/
- "FPL player price changes: how, why and when does it happen?" (3 Oct 2025, previous season): changes happen overnight, and the historical pattern is "a total of £0.3m per Gameweek". https://www.premierleague.com/en/news/2858775

### 1.3 Official API fields (live, public, no auth)

`GET https://fantasy.premierleague.com/api/bootstrap-static/` (≈1.8 MB; `total_players` = 11,303,484 on 2026-11-19).

| Field | Meaning (as observed) |
|---|---|
| `elements[].price_change_percent` | String, e.g. `"97.4"` / `"-94.1"`. Current progress toward a rise (+) or fall (−). ±100 is the threshold. |
| `elements[].price_change_hourly_rate` | Integer, signed. The current pace of progress in the same "units" as the threshold (see §3). |
| `elements[].price_change_projections` | `[{offset:0|1|2, projected_percent, likelihood}]`, one entry per upcoming deadline in `price_change_deadlines`. |
| `…likelihood` | Integer −5…+5. Observed bands: 5 ≥ 100%, 4 ≈ 95–99.9%, 3 ≈ 40–95%, 2 ≈ 20–40%, 1 ≈ 0.1–20%, 0 = 0, mirrored for negatives. The UI maps **+5 "Very likely to rise", +4 "Likely to rise", −4 "Likely to drop", −5 "Very likely to drop"**, and everything else to "Unlikely to change". |
| `elements[].price_change_locked_until` | ISO timestamp or null. Was set only for the two newest Footballers (ids 671, 672). The UI shows "Unlocks in N days". |
| `elements[].price_change_calibrating` | Bool. All `false` by GW10. The UI shows "Calibrating status". |
| `elements[].cost_change_event` / `cost_change_event_fall` | Net price change in the current Gameweek (in £0.1m). It matched the history endpoint for all 672 Footballers. |
| `game_config.settings.price_change_deadlines` | Next 3 deadlines, e.g. `2026-11-20T00:00:00Z`, … |
| `game_config.status.price_change_last_updated` | Timestamp of the last 15-minute refresh (e.g. `17:05:12Z`, then `17:20:12Z`). |

`GET https://fantasy.premierleague.com/api/stats/price-changes/` returns the rolling history of changes. On 2026-11-19 it held 338 rows (252 falls, 86 rises), from 2026-10-08 to 2026-11-19.
- Timestamps are 23:00:0x UTC during BST and 00:00:0x UTC after the 25 Oct clock change.
- `event` is the Gameweek whose deadline has most recently passed, which is the unit the per-Gameweek cap is counted in.

Within this window:
- The maximum was **3 changes for one Footballer in one Gameweek** (N. Jackson and Tavernier in GW8). No case exceeded 3.
- **Two Footballers changed on consecutive nights**, both across a Gameweek boundary (Tavernier: 31 Oct and 1 Nov).

Source: live responses fetched 2026-11-19. Endpoint discovered in the site bundle (`stats/price-changes/`).

---

## 2. Community and reverse-engineered knowledge

| Claim | Status |
|---|---|
| A running net-transfer counter (NTI) moves toward a threshold; on crossing it the price changes by £0.1m and the counter resets; otherwise it carries over. | [COMMUNITY] FFS 2015 guide. **Consistent with official data**: progress persists across days, and Footballers who changed last night now sit at about 0–4%. |
| Rise threshold is a fixed share of active managers (same for everyone). Fall threshold is a share of the Footballer's ownership. | [COMMUNITY] FFS 2015 guide ("2% of active players" and "10% of ownership" as illustrations). **Strongly supported** by §3. |
| Flagged Footballers have a higher fall threshold; red flags highest. | [COMMUNITY] FFS 2015. **Supported** by §3 (`d` ≈1.85×, `i`/`s` ≈2.8×). |
| Thresholds rise for the 2nd and 3rd change in the same Gameweek; historic cap of ±£0.3m per Gameweek. | [COMMUNITY] FFS 2015. Supported by §3 (2nd rise ≈2.7×). The cap is now also [OFFICIAL] in the PL article. |
| Wildcard (and Free Hit) transfers don't count toward price changes. | [COMMUNITY] FFS 2015 ("one theory") and the FFS 2026 article. **Not stated officially; unverified.** |
| New Footballers are locked for about 8 days or until the next Gameweek; locks and flag changes reset NTI. | [COMMUNITY] FFS 2015. The new-player lock is now visible officially (`price_change_locked_until`); the reset-on-flag-change claim is unverified. |
| Old timing ~01:00–03:00 UK. | [COMMUNITY], obsolete for 2026/27 (now 00:00 UK [OFFICIAL]). |
| Prices "don't follow a simple transfer-count threshold". | [COMMUNITY] Fantasy Football Hub (2024), no detail. |

Sources: https://www.fantasyfootballscout.co.uk/2015/08/12/fantasy-premier-league-transfer-market-guide, https://www.fantasyfootballscout.co.uk/2026/07/20/how-do-fpl-price-changes-work, https://www.fantasyfootballhub.co.uk/articles/fpl-price-changes, https://www.fantasyfootballscout.co.uk/2026/08/26/two-up-two-down-fpls-first-price-changes-of-2026-27 (first 2026/27 changes at 00:00 BST on 26 Aug 2026).

---

## 3. What the official numbers reveal (reverse-engineering from one snapshot) [INFERENCE]

**Method.** The projections are a linear extrapolation. `projected_percent[offset k+1] − projected_percent[offset k]` equals 24 h × `hourly_rate` × 100 / T, where T is the number of "units" that make up 100%.
- I checked this on N. Jackson: 6.9 h to midnight × 3,381/h × 100 / 351k ≈ +6.6 percentage points, against 6.6 observed.
- Between the 17:05 and 17:20 refreshes his progress moved 100.3 → 100.6, which also matches 0.25 h × rate / T.

So T_implied = 24 · rate · 100 / Δ. I computed it for every Footballer with |rate| ≥ 15 per hour.

The unit behaves like net transfers. §3.1 shows that 15-minute changes in raw `transfers_in_event − transfers_out_event` match Δprogress × T. Absolute levels differ from the Gameweek counters because progress carries over across Gameweeks and resets only at a price change.

**Results (2026-11-19 17:05 UTC snapshot):**

| Side / situation | Implied T (100%) | Observation |
|---|---|---|
| Rise, no rise yet this Gameweek | **≈128–132k** for nearly everyone, from 0.2% to 54% owned | Flat. ≈1.15% of `total_players`. Flags don't change it (`d`/`i` Footballers also ≈130k). |
| Rise, already +1 this Gameweek (`cost_change_event = 1`) | **≈348–360k** (17 Footballers, very tight) | ≈2.7× the base. |
| Fall, status `a`, no fall this Gameweek | **≈0.105–0.12 × owners** (owners = `selected_by_percent` × `total_players`) | Ownership-proportional, e.g. Dubravka 15.2% owned gives 192k, Palacios 0.1% gives 1.3k. |
| Fall, already −1 this Gameweek | ≈0.18–0.19 × owners | ≈1.7× |
| Fall, status `d` (doubtful) | ≈0.20–0.21 × owners | ≈1.85× |
| Fall, status `i`/`s` (injured/suspended) | ≈0.30–0.34 × owners | ≈2.8× |
| Fall, `i` and already −1 this Gameweek | ≈0.52–0.55 × owners | ≈2.8 × 1.7 (multipliers compose) |
| Fall, status `a`, has risen since season start, no change this Gameweek | Several capped near **≈130k** (Cherki, Ødegaard, Tzolakis, Bogle, Ajayi) | Possibly `min(0.11×owners, rise base)` for some cases. **Unexplained; needs more snapshots.** |

**Caveats.**
- This is one evening's snapshot; per-Footballer estimates are noisy when Δ is small, because `projected_percent` has 0.1 precision.
- The base thresholds will drift as `total_players` grows.
- 3rd-change thresholds were not observable.
- The "units" are FPL's internal measure. I could not confirm that wildcard or Free Hit transfers are excluded.

### 3.1 Second-snapshot check (17:20 → 17:35 UTC refresh)

I compared two consecutive official refreshes for the 23 Footballers with |rate| ≥ 500 an hour. Each 0.1% step of `price_change_percent` equals T/1000 units, so it is about 130 units on the base rise scale and about 352 units after one rise.

- **The progress unit tracks raw net transfers closely.** I compared the change in `transfers_in_event − transfers_out_event` between the two refreshes with Δprogress × T:
  - N. Jackson: +1,406 net against +1,412 units.
  - Wirtz: +398 against +389. Isak: +361 against +352. McGinn: +388 against +354.
  - Fall side: Guéhi −536 against −624; Mbeumo −329 against −236.
  - All agree within the 0.1% rounding of the published percent. **Inference:** progress ≈ Σ(net transfers as reported in `transfers_*_event`) / T. Whether the event counters themselves exclude Wildcard or Free Hit transfers can't be told from outside.
- **`hourly_rate` is a trailing pace, and the evening surge makes it under-predict.** Rates rose 10–40% within 15 minutes (Jackson 3,457 → 3,949 an hour). Observed progress came in at about 1–2.5× what the earlier projection implied. Official `projected_percent` is a straight-line extrapolation, so early-evening projections for "hot" Footballers are conservative and for falling Footballers slightly optimistic. Our alert timing should account for this (§5.1).
- `transfers_in_event` changed for 366 of 672 Footballers between the two refreshes, so the transfer counters and the predictor fields refresh together, every 15 minutes.

---

## 4. Free predictors and reuse

| Predictor | What it offers | Methodology / licence |
|---|---|---|
| **Official FPL Price Changes page** | Progress, predicted progress, likelihood, history; 15-minute refresh | [OFFICIAL] Exposed in the public JSON API (§1.3). Same terms as the rest of the FPL API (see open questions). |
| LiveFPL (livefpl.net/prices) | Progress % plus "progress per hour" to project end of day; tiers Very Likely / Likely / Maybe / Unlikely | Methodology unpublished (described second-hand by FFS). No reuse licence found. |
| FPL Statistics (fplstatistics.co.uk) | "Target" column, where 100 means a likely change | Formula unpublished. No reuse licence found. |
| Fantasy Football Hub | Predictor described as "one of the most accurate", membership toolbox | Methodology unpublished; mostly paywalled. |
| Fantasy Football Fix | Price-change predictor; claimed "around 80% accuracy" (2014) | Paid. |
| OneFPL, FPL Pulse, fplstats.co, onsidearena, etc. | Mirrors or variants | OneFPL's terms: "Do not scrape, overload or attempt to disrupt the service." |

**Conclusion:** no third-party predictor grants a licence to reuse its data, and several sit behind paywalls or anti-scraping terms. Since FPL now publishes the underlying progress itself, there is no reason to touch third-party predictors. At most, link to them for humans.

Sources: https://www.fantasyfootballscout.co.uk/2025/03/03/fpl-price-change-predictions-who-will-rise-fall-on-march-4 (LiveFPL method, second-hand), https://www.fantasyfootballscout.co.uk/2022/11/12/which-fpl-players-could-rise-or-fall-in-price-before-the-world-cup-freeze (FPL Statistics "Target"), https://www.fantasyfootballfix.com/blog-index/so-just-how-accurate-fpl-player-price-changes (Fix ~80%, 2014), https://www.fantasyfootballhub.co.uk/articles/fpl-price-changes, https://onefpl.com/terms, https://onefpl.com/blog/official-fpl-price-predictor-vs-onefpl-market.

Open-source code: a GitHub search (`fpl price change`, `fpl price predictor`) turned up only small, unmaintained or ML-toy repositories (e.g. `RaghavRaina1234/fpl-price-change-predictor`). None implements the official 2026/27 fields or documents a validated threshold model.

---

## 5. Implications for the bot's design

### 5.1 Primary path: use FPL's own predictor (recommended for launch)

The Price alert for a Member is built from the official fields:
- **Owned Footballers at risk:** `projections[0].likelihood ≤ −4`. "Very likely" is −5 (projected ≤ −100%); "Likely" is −4.
- **Watch-list Footballers about to rise:** `projections[0].likelihood ≥ +4`.
- Optionally add an "early warning" tier from `projections[1]`, meaning tomorrow night, with likelihood ≥ ±4.
- Skip Footballers with `price_change_locked_until` in the future, or with `price_change_calibrating = true`.
- Respect the per-Gameweek cap: if |`cost_change_event`| = 3, no further change in that direction this Gameweek.

**Send time.** Late enough to be accurate, early enough to act. Recommendation:
- Send the main alert at about **22:00–22:30 UK**.
- Re-check at about **23:30 UK**.
- Send a short delta only if a Member's Footballer newly crossed ±100% or dropped back below it.

This is a product decision; it belongs to ticket 15 (Price alert spec).

**Selling-price awareness.** The value of a Price alert depends on the Member's purchase price: a rise only adds to selling value on every second £0.1m. This is computable from `selling_price` and `purchase_price` on the Member's own picks; read access depends on ticket 01.

### 5.2 Data snapshots to collect from day one

| Snapshot | Source | Cadence | Why |
|---|---|---|---|
| Price-change fields per Footballer: `id, now_cost, selected_by_percent, status, chance_of_playing_next_round, transfers_in_event, transfers_out_event, cost_change_event, price_change_percent, price_change_hourly_rate, price_change_projections, price_change_locked_until, price_change_calibrating`, plus `total_players` and `price_change_last_updated` | `bootstrap-static` | Every 15 min from about 18:00 to 23:50 UK; hourly otherwise (or skip daytime). Dedupe on `price_change_last_updated`. | Alert inputs; accuracy scoring; fallback model training. |
| Change history | `/stats/price-changes/` | Once a day at about 00:10 UK (after the run) | Ground truth. The endpoint is a rolling window, so archive it. |
| Gameweek deadlines | `bootstrap-static.events` | Daily | Gameweek boundaries reset `cost_change_event`. |

**Volume.** About 672 Footballers × about 25 snapshots a night × about 100 bytes is roughly 1.7 MB a night uncompressed, well within free-tier storage. Ticket 13 (data ingestion) should own the concrete schema.

**Politeness.** One `bootstrap-static` GET every 15 minutes is about 100 requests a day, the same cadence as FPL's own refresh. Use a generic User-Agent with no personal details, and conditional/ETag requests if supported.

### 5.3 Fallback: a home-grown "shadow" predictor (build only if needed)

Used if FPL removes or blanks the fields (for example on a redesign), or to sanity-check the official numbers.

```
State per Footballer f (persisted):
  P_f          # progress in "units" since last change (start from official % × T if available, else 0)
  last_net_f   # last seen (transfers_in_event - transfers_out_event)
  changes_gw_f # cost_change_event (from API)

Each snapshot (every 15 min):
  N      = total_players
  owners = selected_by_percent/100 * N
  d_net  = net_f(now) - last_net_f          # handle GW deadline reset: if counters dropped, d_net = net_f(now)
  P_f   += d_net

  # thresholds (constants fitted nightly from official snapshots; see §3)
  T_rise = a_rise * N * m_rise(changes_gw_f)        # a_rise ≈ 0.0115, m_rise(0)=1, m_rise(1)≈2.7, m_rise(2)=fit
  T_fall = a_fall * owners * m_flag(status) * m_fall(changes_gw_f)
           # a_fall ≈ 0.11, m_flag: a=1, d≈1.85, i/s≈2.8; m_fall(1)≈1.7
  progress = P_f / (T_rise if P_f >= 0 else T_fall) * 100

  rate_h   = EWMA of d_net per hour over the last 3 h (weight recent hours; transfers spike after news, deadlines
             and in the evening; in §3.1 the official linear projection under-shot by ~1-2.5x within 15 min)
  hours    = time to next price_change_deadline
  proj     = (P_f + rate_h * hours) / T * 100

  predict RISE if proj >= 100 and changes_gw_f < 3 and not locked
  predict FALL if proj <= -100 and changes_gw_f > -3 and not locked

After 00:00 UK run:
  read /stats/price-changes/ → for changed f: P_f -= sign * T (or reset to residual); refit a_rise, a_fall, multipliers
  by least squares against the official price_change_percent; log precision/recall per likelihood band.
```

**Calibration trick.** While the official fields exist, `T_official = 24·rate·100/Δprojection` gives an exact per-Footballer threshold every 15 minutes. Fitting `a_rise`, `a_fall` and the multipliers against it is a cheap regression, so the fallback stays calibrated for free.

### 5.4 Expected accuracy

- **Official predictor:** unknown, and FPL disclaims it. It is presumably very good once a Footballer is past 100% late in the evening, because it is FPL's own counter. The failure modes are late-evening transfer surges or reversals (FPL's own 23:45 example) and any "variable factors" outside the progress figure. **We should measure it ourselves** from the snapshots: precision and recall of "±5 at 22:00" and "±5 at 23:45" against `/stats/price-changes/`.
- **Shadow predictor:** bounded above by the official one. Expect it to be worse early in a Gameweek and on flagged or newly added Footballers. Historically, third-party predictors claimed about 80% (Fix, 2014); no recent audited figures exist.

---

## 6. Open questions

1. **What exactly is a "unit"?** Does FPL's counter exclude Wildcard and Free Hit transfers, or transfers by brand-new or inactive managers? Testing needs per-transfer data we can't see. It doesn't matter if we use official progress.
2. **The fall-threshold "cap" anomaly:** some heavily owned Footballers who have risen since the season started show a fall T of about 130k rather than 11% of owners. More snapshots across nights are needed.
3. **Third-change threshold** (2 → 3 in one Gameweek) and the threshold after a change in the opposite direction: not observable in this snapshot.
4. **Does a status change** (flag set or cleared) **reset progress or lock the price?** Only new Footballers showed `price_change_locked_until` today. Watch for locks appearing after flag changes.
5. **FPL Terms & Conditions on API reuse.** The terms page (https://fantasy.premierleague.com/help/terms) is client-rendered and I couldn't read it here. Whether redistributing official predictor numbers in a private, invite-only bot is acceptable should be settled in ticket 16 (security and open-source hygiene) or ticket 01. Low risk for a private advisory bot that doesn't republish data publicly, but unverified.
6. **Stability of the fields.** They are new this season and undocumented. Will they persist into 2027/28? The fallback design hedges this.
7. **The `/stats/price-changes/` window length:** about 6 weeks observed. Is it a fixed day count or a fixed row count? It doesn't matter if we archive daily.

---

## 7. Sources

Official:
- FPL web app and help/rules strings (public JS bundle), fetched 2026-11-19: https://fantasy.premierleague.com/ (pages: /help/rules, /help/new, /price-changes)
- FPL API, bootstrap: https://fantasy.premierleague.com/api/bootstrap-static/
- FPL API, recent price changes: https://fantasy.premierleague.com/api/stats/price-changes/
- Premier League, "What's new in 2026/27 Fantasy: Price Change Predictor" (18 Oct 2026): https://www.premierleague.com/en/news/4680462/whats-new-in-202627-fantasy-price-change-predictor/
- Premier League, "FPL player price changes: how, why and when does it happen?" (3 Oct 2025): https://www.premierleague.com/en/news/2858775
- FPL Terms & Conditions (not readable in this session): https://fantasy.premierleague.com/help/terms

Community / third-party:
- Fantasy Football Scout, "Fantasy Premier League transfer market guide" (12 Aug 2015): https://www.fantasyfootballscout.co.uk/2015/08/12/fantasy-premier-league-transfer-market-guide
- Fantasy Football Scout, "How do FPL price changes work?" (20 Jul 2026): https://www.fantasyfootballscout.co.uk/2026/07/20/how-do-fpl-price-changes-work
- Fantasy Football Scout, "Two up, two down: FPL's first price changes of 2026/27" (26 Aug 2026): https://www.fantasyfootballscout.co.uk/2026/08/26/two-up-two-down-fpls-first-price-changes-of-2026-27
- Fantasy Football Scout, LiveFPL predictions write-up (Mar 2025): https://www.fantasyfootballscout.co.uk/2025/03/03/fpl-price-change-predictions-who-will-rise-fall-on-march-4
- Fantasy Football Scout, FPL Statistics "Target" (Nov 2022): https://www.fantasyfootballscout.co.uk/2022/11/12/which-fpl-players-could-rise-or-fall-in-price-before-the-world-cup-freeze
- Fantasy Football Hub, "How do FPL price changes work?" (May 2024): https://www.fantasyfootballhub.co.uk/articles/fpl-price-changes
- Fantasy Football Fix, "So just how accurate are FPL player price changes" (Oct 2014): https://www.fantasyfootballfix.com/blog-index/so-just-how-accurate-fpl-player-price-changes
- OneFPL terms: https://onefpl.com/terms
- OneFPL, "Official FPL price predictor vs OneFPL market" (Jul 2026): https://onefpl.com/blog/official-fpl-price-predictor-vs-onefpl-market
- LiveFPL prices page (client-rendered, no methodology readable): https://www.livefpl.net/prices
- GitHub search for open-source predictors (e.g. https://github.com/RaghavRaina1234/fpl-price-change-predictor)
