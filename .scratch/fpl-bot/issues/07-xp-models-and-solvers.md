# Open-source expected-points models and transfer solvers to reuse

Type: research
Status: resolved
Blocked by: —

## Question

Which open-source projects can we reuse, or learn from, to compute Expected points and optimise transfers, captain and bench?

Candidates include:
- `sertalpbilal/FPL-Optimization-Tools` and other open FPL solvers
- AIrsenal
- OpenFPL
- the published xP models
- Python mixed-integer programming libraries (HiGHS via `highspy`, PuLP, OR-Tools)

For each, record:
- licence (and whether it fits a public repo)
- maintenance status
- inputs needed
- reported accuracy
- runtime on a free-tier machine

Recommend whether to build our own xP model, reuse one, or combine them. Findings go in `.scratch/fpl-bot/research/07-xp-models-and-solvers.md`.

## Answer

- **Combine:** build our own lightweight component Expected points model, and reuse open-fpl-solver's MIP formulation on HiGHS (`highspy`), vendored behind our own interfaces.
- **Solver:**
  - `sertalpbilal/FPL-Optimization-Tools` now lives at `solioanalytics/open-fpl-solver`. It is Apache-2.0, last committed 2026-09-15, and already handles transfers, rolling free transfers, hits, the XI, captain, vice-captain, bench order and all four Chips.
  - Its input is a simple `{gw}_Pts` / `{gw}_xMins` CSV, and it reads a Squad from the public team-ID endpoints without a login.
  - Its objective is pure xP, so the Mini-league Goal needs our own objective terms.
- **AIrsenal** (MIT, v2.0.0 released 2026-09-25, models defensive contributions) is the best design to learn from: a team goals model, then each Footballer's share of goals, then a minutes model, then point components, plus backtests. Its authors report 0.90 MAE and 0.816 rank correlation on 2025/26. As a whole it is too heavy to adopt: its own SQLite database, JAX and NumPyro, and an exhaustive tree-search optimiser.
- **OpenFPL** (MIT) roughly matches FPL Review's paid model on 3+ point outcomes but is worse on 0–2. Its models predate defensive-contribution scoring and the 2026/27 BPS changes, it needs scraped Understat data, and it was last committed in August 2025. Use its ideas and evaluation buckets, not its models.
- **Minutes is the main accuracy lever** and the natural place for Scout-mode adjustments. Keep FPL's own `ep_next` and a last-5 average as baselines for self-evaluation.
- **MIP library:** use `highspy` 1.16.0 (MIT, aarch64 and Python 3.14 wheels). Not PuLP: from 4.x it no longer bundles CBC.
- **Runtime:** no project publishes solve times. A timing spike on the Oracle A1 host is the main open question.
- Findings: [../research/07-xp-models-and-solvers.md](../research/07-xp-models-and-solvers.md)
