# 46: football-data.co.uk adapter and team ratings

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the second data source and the team strengths the xP model starts from.
- A fail-soft adapter for the current-season football-data.co.uk CSV, fetched daily at 06:00 UK through the polite client (generic User-Agent, its own 1 req/s limit because it's a different host, same retry and 403 rules).
- A pure function in `prediction` that fits attack and defence ratings per club, with one global home-advantage term, from results, closing odds and (from 2026/27) match xG, blended with FPL's xG and xGC from stored stats. It returns expected goals for and against for every scheduled fixture.
- Only the derived aggregates are stored (team ratings per run, per-fixture expected goals), with a season column. The raw CSV is never stored or committed.
- Completion row `odds` per day. If the source is down, the last ratings stay in use; after 2 days in a row the owner gets one deduplicated DM, and a "recovered" DM when it comes back.

**Blocked by:** 44: Phase 1 review leftovers

**Status:** open

- [ ] A recorded CSV fixture drives the tests; no test touches the network.
- [ ] Ratings are deterministic for a fixed input, and a stronger club in the fixture gets higher expected goals.
- [ ] Missing columns (no match xG in older files) fall back to results and odds without failing.
- [ ] Source down for 1 day: no DM; 2 days: one DM; back up: one "recovered" DM.
- [ ] No raw CSV row is stored anywhere.
