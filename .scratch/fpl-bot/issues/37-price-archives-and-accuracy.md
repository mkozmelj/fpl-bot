# 37: Price archives and `/accuracy`

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** the owner can judge FPL's price predictor, and the price and news history the later phases need is kept.
- Price snapshots: `bootstrap-static` at 18:00, 20:00, 22:00, 23:00 and 23:45 UK; one compact row per Footballer (price, percent, hourly rate, the 3 likelihoods, lock flags). Missed snapshots are skipped, never back-filled.
- At 00:05 UK a fresh `bootstrap-static`, and at 00:10 the `/stats/price-changes/` archive, stored as Price changes with a `price_archive` completion row per night.
- At each Price-alert time, store every Footballer's projection code beside the alert's night, so it can be matched to the actual change.
- A news and status change log from hourly `bootstrap-static` reads 08:00-23:00 UK, written only when something changed.
- Owner-only `/accuracy`: hit rate per projection code (−5..+5) for tonight and for tomorrow, plus a season total. A flag when ±4 is below 70% or ±5 below 85% over a rolling 14 nights with at least 20 predictions per bucket. Threshold changes stay manual. Members never see any of it.

**Blocked by:** 36: Nightly Price alert

**Status:** resolved

- [ ] After fake-clock nights with recorded price-change fixtures, `/accuracy` shows hit rates per code for tonight and tomorrow and a season total.
- [ ] The floor flag appears only when a bucket has at least 20 predictions over 14 nights and falls below its floor.
- [ ] `/accuracy` from a Member gets no reply.
- [ ] Re-running the 00:10 archive for a night is a no-op.
- [ ] The news log gains a row only when a Footballer's news or status changes.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in e1d4eed; review fix-ups in 1004dd3). Tests live in `core/tests/`.
