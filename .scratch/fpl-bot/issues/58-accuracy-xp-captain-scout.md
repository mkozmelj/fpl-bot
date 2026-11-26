# 58: `/accuracy xp`, `captain` and `scout`

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** owner-only reports on the bot's own predictions. No Member tracking.
- `/accuracy` alone lists the four views; the existing Price-alert view moves to `/accuracy price`.
- `xp`: per finished Gameweek and season to date, MAE and rank correlation of the deadline −90 run for Core, Baseline and the stored `ep_next`.
- `captain`: per Gameweek, the bot's Overall rank pick, the top-xP pick, FPL's most-captained Footballer and `ep_next`'s pick, each with realised points. It never says what a Member captained.
- `scout`: minutes MAE and xP MAE with no overrides, with regex and with regex plus Claude, the number of affected Footballer-Gameweeks, and whether Claude-derived overrides meet the bar to be switched on.
- The owner gets one DM when the backtest-or-live bar status changes (Core starts or stops beating `ep_next` on the season to date).

**Blocked by:** 51: `/captain` for the Overall rank Goal; 56: Claude Scout leftovers

**Status:** open

- [ ] Each view renders from fixture data after two finished Gameweeks.
- [ ] Non-owners get no reply to any `/accuracy` form.
- [ ] `/accuracy price` matches the Phase 1 output.
- [ ] The scout view says plainly whether the Claude bar is met.
- [ ] No query reads Member picks for the captain report.
