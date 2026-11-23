# Expected-points model design

Type: grilling
Status: resolved
Assignee: owner
Blocked by: —

## Question

Given [How the best FPL managers make decisions in 2026](05-elite-manager-methods.md), [Open-source expected-points models and transfer solvers to reuse](07-xp-models-and-solvers.md), [Free, legal football stats sources for predictions](02-free-stats-sources.md) and [Which data the bot collects, how often, and what it keeps](13-data-ingestion-design.md), how does our component xP model work? Decide:
- Inputs per Footballer and fixture (FPL xG/xA/xGC/defensive contribution, odds CSV, set-piece order).
- The minutes model, the main accuracy lever.
- The horizon and decay, and how double and blank Gameweeks enter.
- How Scout adjustments (news flags, Member-pasted notes) plug in.
- The backtest method against vaastav data and the `ep_next` baseline, and the accuracy bar to pass.
- Where it lives in the `fplbot` module split.

## Answer

- **Shape:** a component model in AIrsenal's style: team goals, then each Footballer's share of goals and assists, then minutes, then point components (appearance, goals, assists, clean sheet, saves, bonus, defensive contribution, cards). The simple blend of FPL's `ep_next` rescaled plus a last-5 average stays as the always-on Baseline, and is also the Baseline Ghost Squad.
- **Method:** plain and explainable: Poisson and shrunk per-90 rates, with team attack and defence strength from the odds CSV and FPL xG/xGC. NumPy/SciPy only, with no ML framework, JAX or NumPyro. Revisit only if the backtest demands it.
- **Minutes:** the main accuracy lever. Expected minutes = start probability × expected minutes if started. Inputs are recent starts and minutes, `chance_of_playing_*`, `status`, rotation risk from fixture congestion and lineup stability. Scout adjustments plug in only here, as overrides to start probability and minutes. The output feeds the solver's `xMins` directly.
- **Horizon:** store raw per-Gameweek xP for **5 Gameweeks**. The planner applies decay (0.85) on a planning horizon of 5. Horizon is a setting, and **3 and 8** are compared in the backtest. The default moves only on a clear win. Blank Gameweeks give 0 and double Gameweeks sum per-fixture xP. (Elite evidence: FPL Review uses 6 and decay 0.85, the last three champions plan about 5–6 ahead, and only the solver default is 8.)
- **Backtest:** vaastav 2024/25 and 2025/26 against `ep_next` and last-5, on MAE and rank correlation, with OpenFPL's 0–2 vs 3+ point buckets as a secondary view. **Bar to ship:** beat `ep_next` on both metrics out of sample. Live, xP is compared with realised points each Gameweek, owner-only and with no Member telemetry. Core versus Baseline Ghost Squads are the end-to-end check from 2026/27.
- **Where it lives:** the `prediction` module of `fplbot`, as a pure function. It takes a data snapshot plus Scout overrides and returns a table of per-Footballer, per-Gameweek xP and xMins, with no database access. `optimisation` consumes the table. This keeps it testable and replayable.
