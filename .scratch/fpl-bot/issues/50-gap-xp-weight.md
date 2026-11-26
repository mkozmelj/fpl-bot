# 50: Gap weighted by xP

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the Elite gap and Rival gap use next-Gameweek xP from the model in use as the weight, instead of the average of the last 4 finished Gameweeks. `advice/gap.py` doesn't change; the jobs and delivery pass the new weight.
- The header says "weighted by xP (Core)" or "weighted by xP (Baseline)".
- The recent-points weight is removed, along with `RECENT_GAMEWEEKS` and its query.

**Blocked by:** 49: xP job, storage and `/status`

**Status:** open

- [ ] `/gap`, `/gap captain` and `/rivals` use next-Gameweek xP; a Footballer with a blank Gameweek has weight 0 and never qualifies.
- [ ] The header names the model in use.
- [ ] All Phase 1 Gap scenarios (thresholds, partial and stale labels, no Elite data, between-deadline caveat) still pass with the new weight.
- [ ] No code path still reads the last-4 average.
