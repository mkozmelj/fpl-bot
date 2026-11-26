# 49: xP job, storage and `/status`

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the scheduled job that runs the model and keeps its output.
- Runs after `gw_final` completes, daily at 06:30 UK (after the 06:00 odds fetch), and at deadline −90 minutes. Builds the snapshot from the store and in-memory `bootstrap-static`, runs Core and Baseline, and stores both tables with a run ID, marking one current.
- Stores `ep_next` per Footballer for the coming Gameweek at the deadline −90 run.
- Keeps the last 2 runs plus each Gameweek's deadline −90 run; prunes older runs. Batched writes.
- A setting chooses the model advice uses (`Core` or `Baseline`); it ships as `Baseline`.
- Completion row `xp` per trigger; startup catch-up reruns a missed morning run, and a missed deadline −90 run only if the deadline hasn't passed.
- `/status` adds the last xP run (time and model in use) and the next scheduled runs.
- On failure the owner gets one deduplicated DM, and advice keeps using the previous current run.

**Blocked by:** 45: Extra FPL fields, stable Footballer code and prior-season rates; 46: football-data.co.uk adapter and team ratings; 47: Expected-points model (pure) and the Baseline

**Status:** open

- [ ] Each trigger runs once and writes one run; a re-run of the same trigger is a no-op.
- [ ] A restart after a missed morning run catches it up; a deadline −90 run missed past the deadline is skipped.
- [ ] Pruning keeps exactly the runs the spec names.
- [ ] A failing model run sends one owner DM and leaves the previous run current.
- [ ] `/status` shows the new lines.
- [ ] Storage per season stays small enough for Neon's free tier (assert row counts in a test).
