# How FPL price changes work and how to predict them

Type: research
Status: resolved
Blocked by: —

## Question

How do FPL Price changes work in 2026/27, and how do existing predictors forecast them?

Cover:
- What is known or reverse-engineered about the algorithm: net transfers relative to ownership, thresholds, the daily ~01:30 UK update, maximum moves per Gameweek, wildcard and free-hit transfers being excluded, flagged Footballers, and protection after a change.
- Which free predictors exist (for example LiveFPL, FPL Statistics, Fantasy Football Hub, fplpricechanges-style sites), and whether their data can be legally reused.
- What data we'd need to build our own predictor (snapshots of `transfers_in_event`/`transfers_out_event`, polling cadence) and the accuracy it can realistically reach.

Findings go in `.scratch/fpl-bot/research/04-price-change-mechanics.md`.

## Answer

- **New for 2026/27: FPL publishes its own Price change predictor in the public API.** `bootstrap-static` now carries `price_change_percent`, `price_change_hourly_rate`, `price_change_projections` (the next 3 nightly deadlines, each with a likelihood code from −5 to +5), `price_change_locked_until` and `price_change_calibrating`. It refreshes every 15 minutes. `/api/stats/price-changes/` gives a rolling ~6-week history of actual changes.
- **Official rules:** changes happen once a day at 00:00 UK (no longer ~01:30), at most £0.1m a day, and up to £0.3m per Gameweek according to a premierleague.com article. Sellers keep half of any rise. FPL says the formula "won't be revealed".
- **What the official numbers imply (inferred from live snapshots):**
  - Progress is accumulated net transfers. It carries over between days and resets at a change.
  - The rise threshold is flat, about 130k net transfers (≈1.15% of managers) whatever the ownership, and about 2.7× that after a rise in the same Gameweek.
  - The fall threshold is about 11% of current owners, multiplied by about 1.7 after a fall in the same Gameweek, about 1.85 for doubtful (`d`) and about 2.8 for injured or suspended (`i`/`s`) Footballers. This matches the long-standing community theory.
- **Protection:** newly added Footballers are price-locked. There is no multi-day lock after an ordinary change. The Wildcard/Free Hit exclusion is community lore only; FPL never states it for prices.
- **Third-party predictors** (LiveFPL, FPL Statistics, Fantasy Football Hub, Fix, OneFPL) publish neither a methodology nor a reuse licence, and some forbid scraping. Don't reuse them.
- **Recommendation:** base the Price alert on the official `price_change_projections` (±5 Very likely, ±4 Likely). Snapshot `bootstrap-static` every 15 minutes in the evening and archive the history endpoint daily, so we can measure the official predictor's accuracy. Keep a calibrated "shadow" predictor only as a fallback in case the fields disappear.
- Details, algorithm sketch, snapshot list and open questions: [../research/04-price-change-mechanics.md](../research/04-price-change-mechanics.md)
