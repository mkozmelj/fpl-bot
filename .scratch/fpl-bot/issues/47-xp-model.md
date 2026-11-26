# 47: Expected-points model (pure) and the Baseline

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the xP model as a pure function in `prediction`, plus the Baseline, with no database, clock or network.
- Input: a data snapshot (Footballers, fixtures with expected goals, per-Gameweek stats, priors, news state, the season's scoring rules) and a set of overrides. Output: per Footballer, per Gameweek, per fixture xP and xMins for the next 5 Gameweeks, plus the decayed 5-Gameweek sum (decay 0.85).
- Components in AIrsenal's style: team goals, the Footballer's share of goals and assists, minutes, then point components (appearance, goals, assists, clean sheet, goals conceded, saves, bonus, defensive contribution, cards). Poisson rates; per-90 rates shrunk toward position and club priors. NumPy and SciPy only.
- Minutes = start probability × expected minutes if started, from recent starts and minutes, `chance_of_playing_*`, `status`, congestion and lineup stability. Overrides change start probability and minutes-if-started only.
- Scoring rules are an input, so 2024/25 (no defensive contribution) and later seasons both score correctly.
- Baseline: `ep_next` rescaled, blended with a last-5 average, returned in the same table shape.
- Every tunable (horizon, decay, shrinkage strengths, minutes thresholds) lives in one settings module.
- This is the spec's second test seam: pure-function tests with small hand-built snapshots.

**Blocked by:** None (can start immediately; use hand-built snapshots until 45 and 46 land)

**Status:** open

- [ ] Blank Gameweek gives 0; double Gameweek sums per-fixture xP.
- [ ] Start probability 0 gives 0 xP; an override that sets minutes to 0 does the same.
- [ ] A Footballer with few minutes is pulled toward the prior; one with many is barely moved.
- [ ] 2024/25 rules give no defensive-contribution points; 2025/26 rules do.
- [ ] Output is identical for identical input.
- [ ] The Baseline returns the same shape and runs with only FPL fields.
- [ ] One full run over about 700 Footballers and 5 Gameweeks takes well under 10 s on 1 vCPU.
