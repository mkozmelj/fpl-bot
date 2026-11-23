# 30: `/squad` and join backfill

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a Member sees the Squad the bot is basing its output on. When a Member finishes linking their team, the bot fetches their season history and past picks (launch backfill per the spec). `/squad` shows the Squad as of the last deadline: XI by position, bench, captain and vice-captain. Between deadlines it says that this Gameweek's picks are hidden by FPL until the deadline.

This ticket also starts the reference data kept across seasons: Footballers, clubs, fixtures and Gameweeks, refreshed from `bootstrap-static` and fixtures.

**Blocked by:** 28: Join flow, settings and `/leave`

**Status:** ready-for-agent

- [ ] After joining, `/squad` shows the last-deadline Squad with captain and vice-captain marked.
- [ ] Before the next deadline the message states which Gameweek the Squad is from and that the upcoming Gameweek's picks are hidden until its deadline.
- [ ] A Member whose picks for a Gameweek are missing (fixture with hidden picks) gets a clear message, not an error.
- [ ] Member history and picks are deleted on `/leave`.
- [ ] Command name follows the prototype (`/squad`).
