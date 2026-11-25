# 31: Post-deadline picks job, scheduler and startup catch-up

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** after every deadline the bot picks up each Member's locked Squad on its own, and never loses a Gameweek to a restart.
- APScheduler with no persisted job store: jobs are rebuilt from the DB and the FPL deadlines at startup and after each data refresh, with a misfire grace window.
- The post-deadline job starts at deadline +5 minutes with one cheap probe. While FPL answers "updating", it waits 10 minutes and probes again (not counted as backoff tries).
- It refreshes Member picks for the new Gameweek and writes a `picks` completion row for that Gameweek. Later tickets extend this job with Rival picks (33) and the Elite cohorts and sample (34), in the spec's order: Elite standings, then Member and Rival picks, then the Elite sample.
- Jobs are idempotent. At startup the bot runs anything missing for the current and previous Gameweek.
- `bootstrap-static` refreshes at deadline -90 min, -30 min and just after.

**Blocked by:** 27: Polite FPL client and owner incident DMs; 30: `/squad` and join backfill

**Status:** resolved

- [ ] With a fake clock passing a deadline, `/squad` afterwards shows the new Gameweek's Squad without any Member action.
- [ ] While the fixture answers "updating", the job waits and re-probes, then completes once FPL answers.
- [ ] Re-running the job for a completed Gameweek changes nothing visible and sends nothing.
- [ ] Starting the bot after a missed deadline catches up the current and previous Gameweek.
- [ ] A 403 during the job pauses it until its next run and DMs the owner once (via ticket 27).

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in ea1ab84; review fix-ups in 1004dd3). Tests live in `core/tests/`.
