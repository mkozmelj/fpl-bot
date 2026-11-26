# 45: Extra FPL fields, stable Footballer code and prior-season rates

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the FPL data the xP model needs that Phase 1 doesn't keep.
- `footballers` gains FPL's stable `code`, so a Footballer can be matched across seasons (element IDs are renumbered each season).
- `footballer_gameweek_stats` gains `defensive_contribution`, `yellow_cards`, `red_cards`, `own_goals`, `penalties_missed` and `penalties_saved` from `event/{gw}/live`. The launch backfill re-reads finished Gameweeks once to fill them.
- `footballer_news` gains `chance_of_playing_this_round` and `chance_of_playing_next_round`, still written only when something changed.
- A snapshot reader for `bootstrap-static` exposes `ep_next`, `chance_of_playing_*` and set-piece order (`penalties_order`, `direct_freekicks_order`, `corners_and_indirect_freekicks_order`) to jobs. Held in memory, not stored raw.
- Prior-season per-90 rates: once a season (and once at first run), fetch `element-summary/{id}` for every Footballer at the sampler's low priority (about 700 requests) and store the `history_past` row for the previous season, keyed by `code`. Idempotent with a completion row `priors`.

**Blocked by:** 44: Phase 1 review leftovers

**Status:** open

- [ ] New columns are added by backward-compatible migrations; recorded fixtures carry the new fields.
- [ ] Missing fields (older seasons, FPL omissions) are stored as NULL, never as 0.
- [ ] The priors job runs at the lowest limiter priority and never delays an interactive command or the Price alert in tests.
- [ ] Re-running the priors job does no extra requests once complete; startup catch-up resumes a partial run.
- [ ] A news row is written when only `chance_of_playing_*` changes.
- [ ] Nothing raw is stored; only the listed columns.
