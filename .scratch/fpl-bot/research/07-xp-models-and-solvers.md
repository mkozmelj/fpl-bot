# Open-source Expected points models and transfer solvers to reuse

Research for ticket `issues/07-xp-models-and-solvers.md`. Researched 2026-11-19 (2026/27 season). Repo metadata comes from the GitHub API on that date. No code was cloned or run.

How to read the labels:
- **[fact]** means I checked it myself in a primary source: the repo's files, the GitHub API, PyPI, the FPL API or official docs.
- **[author]** means the project's authors claim it and I did not reproduce it.
- **[inference]** means it is my own reasoning.

Sources are listed as `[S#]` at the end.

Note on the date: the FPL API on 2026-11-19 shows Gameweek 10 as current and **Gameweek 11 as next** (deadline 2026-11-21 11:00 UTC), not GW12 [fact, S20].

## TL;DR

- **Solver: reuse the open-fpl-solver formulation and run it on HiGHS via `highspy`.** `sertalpbilal/FPL-Optimization-Tools` now redirects to `solioanalytics/open-fpl-solver`. It is Apache-2.0, its last commit was 2026-09-15, and it is a deterministic multi-Gameweek MIP. One model covers transfers, hits, rolling free transfers, the starting XI, captain, vice-captain, bench order and all four Chips. It takes any Expected points (xP) CSV with `ID`, `Pos`, `{gw}_Pts` and `{gw}_xMins` columns [fact, S1–S4].
- **Its objective is pure discounted xP.** Bench slots and the vice-captain get fixed weights [fact, S4]. A Mini-league Goal (Rival gap) and our own valuation of rolling transfers will need changes to the objective. So we should vendor or fork the formulation rather than call it as a black box [inference].
- **No open project gives a ready-made xP we can just use for 2026/27.**
  - **OpenFPL** is MIT and a good paper, but its models were trained on 2020/21–2023/24. That is before FPL's defensive-contribution points (from 2025/26) and before the 2026/27 BPS tweaks. It also needs scraped Understat data, and its last commit was 2025-08-15 [fact, S7–S10, S21, S22].
  - **AIrsenal** is MIT, actively maintained (v2.0.0 on 2026-09-25) and does model defensive contributions. But it is a whole app: its own SQLite database, plus JAX and NumPyro, plus a slow exhaustive tree-search optimiser [fact, S5, S6].
- **Reported accuracy, for scale.**
  - AIrsenal's default model: points MAE 0.90, RMSE 1.88 and rank correlation 0.816, over all Footballers, 2025/26 GW5–30 [author, S6].
  - OpenFPL vs FPL Review's paid model (2024/25 GW32–38, 1-GW RMSE): about equal on 3–4-point "tickers" and ≥5-point "haulers" (OpenFPL slightly ahead), but worse on 0–2-point outcomes. The authors put that down to having no expected-minutes input [author, S8].
  - The two sets of numbers are **not comparable**: different seasons, samples and metrics [inference].
- **Minutes is the biggest lever.** OpenFPL's own diagnosis is missing xMins. FPL Review's edge is a simulated, news-adjusted xMins that users can override [author, S8, S19]. That fits Scout mode: adjust minutes first, then xP [inference].
- **Free baseline already in hand:** the FPL API's `ep_this` and `ep_next` fields exist for every Footballer [fact, S20]. FPL does not document how they are computed (no primary source found). Use them only as a benchmark to beat [inference].
- **MIP libraries:**
  - `highspy` 1.16.0 is MIT, released 2026-11-11, with wheels for Linux aarch64 and Python 3.14, so it runs on the Oracle A1 host [fact, S11, S12].
  - PuLP 4.x is MIT but **no longer bundles CBC**; you need `pulp[cbc]`, and CBC is EPL-2.0 [fact, S13, S14].
  - OR-Tools 9.15 is Apache-2.0, but its latest release is 2026-01-12 [fact, S15].
  - Pick `highspy` directly, which is what open-fpl-solver already uses [inference].
- **Runtime on a free-tier machine: no project publishes solve times.**
  - open-fpl-solver defaults to a 600-second limit and a 0% optimality gap [fact, S3].
  - AIrsenal's README only says the transfer search "will take a while" [author, S5].
  - A short timing check on the target host is needed (see Open questions) [inference].
- **Recommendation: combine.** Build our own lightweight component xP model, borrowing AIrsenal's structure and point maths (MIT) and OpenFPL's evaluation buckets and feature ideas. Reuse open-fpl-solver's MIP (Apache-2.0) on `highspy`, behind our own interfaces.

## Comparison table

| Candidate | What it is | Licence (public-repo fit) | Maintenance (2026-11-19) | Inputs needed | Reported accuracy | Free-tier runtime |
|---|---|---|---|---|---|---|
| **open-fpl-solver** (formerly `sertalpbilal/FPL-Optimization-Tools`) | Deterministic multi-GW MIP solver; no xP model | Apache-2.0 [S1]. Fits: fork or vendor with licence and notice of changes [inference] | Last commit 2026-09-15; 192★; 3 open issues; maintained by Chris Musson; repo now under the `solioanalytics` org [fact, S1, S2] | Projection CSV (`ID`, `Pos`, `{gw}_Pts`, `{gw}_xMins`) + FPL `bootstrap-static` and `fixtures`. Squad from a public team ID (rebuilds selling prices and free transfers from public transfers and history) or from a `my-team` JSON copied while logged in [fact, S3, S4] | n/a (solver). Optimal for the given xP when `gap: 0` [fact, S3] | Not published. Default `secs: 600`, `gap: 0`, `horizon: 8` [fact, S3]. Needs Python ≥3.14 [fact, S16] |
| **AIrsenal** (Alan Turing Institute) | Full pipeline: DB, xP model, transfer and squad optimiser, apply to FPL | MIT [S5]. Dependency DEAP is LGPL-3.0 [fact, S17]. Fine as a library or for borrowing code with attribution [inference] | v2.0.0 released 2026-09-25; daily bot commits; human merges 2026-11-13; 355★; 77 open issues [fact, S5] | FPL API + 3 past seasons packaged in the repo (built with help from vaastav data) + FIFA team ratings for promoted clubs + Transfermarkt absences. FPL login only to see same-GW changes or to apply transfers [fact, S5, S6] | Points MAE 0.900, MAE when the Footballer appeared 2.08, RMSE 1.880, rank correlation 0.816 (2025/26 GW5–30, xG team model with Conway-Maxwell-Poisson) [author, S6] | Not published. "This will take a while" [author, S5]. Optimiser enumerates every legal move per GW, multi-process [fact, S18]. Heavy stack (JAX/NumPyro) [fact, S16] |
| **OpenFPL** (Groos, arXiv 2508.09992) | Per-position XGBoost and random-forest ensembles (median of 50 models); xP only, no solver | Code MIT [S7]; paper CC BY 4.0 [S8]; search framework KBestSearch is Apache-2.0 [S17] | Last commit 2025-08-15; 28★; issue #5 (missing scaler files) answered by the author as fixed on main [fact, S7, S9] | 196–206 features per position: FPL API stats + **Understat** player and team stats (xG, xA, xGChain, PPDA…), averaged over 1/3/5/10/38 matches [author, S8]. The historical data "is property of" FPL and Understat [fact, S10] | 1-GW RMSE vs FPL Review: zeros 0.818 vs 0.689; blanks 1.291 vs 1.189; tickers 1.517 vs 1.594; haulers 5.142 vs 5.172 (2024/25 GW32–38 only) [author, S8] | Not stated in the paper [fact, S8]. Inference on about 700 Footballers should be cheap; training is the heavy part [inference] |
| **FPL API `ep_this` / `ep_next`** | FPL's own one-GW expected points | FPL's data; no licence stated | Live; present on 2026-11-19 [fact, S20] | None (one field per Footballer) | Not documented [fact: no source found] | Free |
| **FPL Review** (commercial) | xP and xMins model plus web solver | Proprietary. Free model has a 3-GW horizon; CSV export is premium (Patreon) [fact, S19b, S19c] | Active | — | Used as the benchmark in OpenFPL [S8] | — |
| **Solio / Transfer Algorithm ("Mikkel")** (commercial) | Paid projection sheets that open-fpl-solver can read | Proprietary [S3, S23] | Active | — | — | — |
| **penaltyblog** | Football models library (Poisson, Dixon-Coles, Bayesian, ratings), scrapers, fantasy optimiser | MIT [S24] | Last push 2026-10-19; 249★ [S24] | Match results / xG | Not FPL-xP specific | Cython; light [author, S24] |
| **HiGHS / `highspy`** | Open MIP/LP solver | MIT [S11] | 1.16.0, 2026-11-11; aarch64 and cp314 wheels [fact, S12] | — | — | Native; no subprocess [fact, S4] |
| **PuLP** | Modelling layer | MIT; CBC extra is EPL-2.0 [S13, S14] | 4.3.1, 2026-11-19 [S12] | — | — | CBC no longer bundled [fact, S13] |
| **OR-Tools** | CP-SAT / MIP wrappers | Apache-2.0 [S15] | v9.15, 2026-01-12 [S15] | — | — | Overkill for this model size [inference] |

Smaller repos (spinalwiz/fpl-optimiser, Fournierp/FPL, elcaiseri/OpenFPL-Scout-AI and others) are either inactive, unlicensed, or toy models without published held-out accuracy. For example, OpenFPL-Scout-AI's squad picker is "intentionally budget-free" [fact, S25]. **Do not confuse elcaiseri/OpenFPL-Scout-AI with Groos's OpenFPL.**

## Recommendation: combine

**1. Solver: reuse open-fpl-solver's formulation, owned in our repo.**
- **Why** [fact unless marked]:
  - It already models exactly what Phases 2 and 3 need: XI, captain, vice-captain, bench order, multi-GW transfers with rolling free transfers and hits, WC/FH/BB/TC, banned and locked Footballers, and booked transfers [S3, S4].
  - It runs on `highspy`, so there is no external binary [S4, S26].
  - It reads a simple CSV contract [S4].
  - It is Apache-2.0 [S1].
- **Why not call it unchanged** [inference]:
  - It is a 53 KB single-function script that reads files from `data/`. It defaults to Solio's paid CSV and needs Python ≥3.14 [fact, S2, S3, S16].
  - Its objective has no way to express Mini-league Goal terms.
- **Plan** [inference]: vendor `dev/solver.py` into a `solver` module with an Apache-2.0 notice. Feed it our xP in its CSV/DataFrame shape. Add objective hooks for Goal-dependent terms. Keep the upstream repo as the regression oracle.

**2. xP: build our own lightweight component model, learning from AIrsenal and OpenFPL.**
- **Why not reuse AIrsenal wholesale** [inference]:
  - It brings its own SQLite schema, ingestion, Transfermarkt and FIFA scraping, and JAX/NumPyro, which duplicates our Neon ingestion.
  - Its optimiser is an exhaustive tree search, which we don't need once we have the MIP [fact for the design, S6, S18].
- **What to borrow, MIT with attribution** [inference]:
  - The decomposition: team goals model → player share of goals → minutes model → point components [fact for the design, S6].
  - Its finding that an xG-fitted team model mainly improves defending points [author, S6].
  - Its backtest metrics (MAE, MAE when appeared, RMSE, rank correlation, minutes-band accuracy) [author, S6].
- **Why not reuse OpenFPL** [inference from fact]:
  - Its targets predate defensive-contribution scoring (2025/26) and the 2026/27 BPS changes [S21, S22].
  - It includes models for the Assistant Manager chip, which has since been scrapped [S8, S22].
  - It depends on scraped Understat data [S8, S10].
  - Retraining is possible (Apache-2.0 KBestSearch), but it needs a multi-season Understat history.
- **What to borrow from OpenFPL** [inference]:
  - Its outcome buckets (zeros / blanks / tickers / haulers), which are a better self-evaluation lens than plain RMSE.
  - Its lesson that low-return error comes from minutes.
- **Baselines** for "Prediction self-evaluation": `ep_next` [S20] and a "last-5 average" (which OpenFPL shows is worse than both models [author, S8]) [inference].

**3. Optional shortcut for Phase 2** [inference]: if building xP slips, AIrsenal's `predict` could be run offline as a stopgap, since its prediction layer is pluggable through protocols [author, S6]. But it would still need its own database.

## Implications for the bot's design

- **One xP contract between the model and the solver** [inference]: a per-Footballer, per-GW table of `xP` and `xMins` (and optionally P(60+ minutes)), keyed by the FPL element ID. That matches the open-fpl-solver columns [fact, S4]. Scout mode adjusts xMins and xP in this table before solving. So Analyst mode stays "plain code computes, Claude explains".
- **Minutes model first.**
  - AIrsenal's default minutes model takes the last N matches as equally likely. It sets Footballers with ≤50% chance of playing to 0 minutes [fact, S6].
  - FPL Review's xMins is a probability-weighted simulation with news overrides [author, S19].
  - Our minutes model is where Scout mode adds value [inference].
- **2026/27 scoring components** [fact for the rules, inference for the design]:
  - The model needs a defensive-contribution component (2 points; midfielders and forwards need 12 CBIRT [S21]; the 10-CBIT threshold for defenders comes from secondary coverage only). AIrsenal already has `def_con` [S6].
  - Bonus must reflect the 2026/27 BPS update (secondary sources only) [S22].
  - There are two sets of Chips, one per half of the season; the API lists two of each [fact, S20].
- **Goal handling** [inference]:
  - The Overall-rank Goal is the solver's native objective: maximise xP.
  - The Mini-league Goal needs extra objective terms, for example weighting Footballers by Rival ownership or captaincy, as Gap-aware swing. That is a reason to own the solver code.
  - Captain and bench logic can be the same MIP with horizon 1 and transfers locked.
- **Squad reading without a password** [fact, S4]: open-fpl-solver rebuilds bank, selling prices and free transfers from the public `entry/{id}/transfers`, `history` and `picks` endpoints. That fits Advice mode. Transfers a Member makes after the deadline won't show until the next Gameweek. Its `my-team` route needs the Member's own logged-in browser [fact, S4], so the bot must not use it [inference].
- **Host** [inference]: `highspy` and `jaxlib` both ship Linux aarch64 wheels [fact, S12]. The solver will install on the Oracle A1 VM chosen in ticket 09. Cap each solve with `time_limit` and a small `mip_rel_gap` so 5–10 Members finish well before the deadline.
- **Robustness**: open-fpl-solver can add noise to xP scaled by xMins and run repeated simulations to test how stable a plan is [fact, S4]. That is useful for "how confident is this transfer" explanations [inference].
- **Licensing hygiene**: keep the Apache-2.0 and MIT notices for vendored code. Don't commit scraped Understat or FPL data to the public repo; vaastav's licence notes the data belongs to FPL and Understat [fact, S10] [inference for the policy].

## Open questions

1. **Solve time on the target host.** How long does the vendored solver take on Oracle A1 (2 OCPU / 12 GB) for horizons of 1, 4 and 8 Gameweeks, with gap 0 and with gap 0.5%? None of the sources publish this. The ticket forbade running code, so it needs a short spike.
2. **Accuracy target.** Which bar must our xP beat to count as good enough for Phase 2: `ep_next`, a last-5 average, or AIrsenal's 0.90 MAE on a 2026/27 backtest? The bar decides how much modelling to build.
3. **Understat.** Do we use it at all, given its access terms and the scraping it requires? This depends on ticket 02 (free stats sources). The FPL API already carries xG, xA, xGC and defensive contributions per Footballer [fact, S20].
4. **Repo stewardship.** Why did the solver move to the `solioanalytics` org, and will future releases stay Apache-2.0? Today's licence still lets us fork [fact, S1], but a future relicence would affect upstream fixes.
5. **`ep_next` methodology** is undocumented. Is it worth reverse-engineering, or should it only serve as a baseline?

## Sources

- [S1] GitHub API, repo `sertalpbilal/FPL-Optimization-Tools` → `solioanalytics/open-fpl-solver` (licence, push date, stars, issues), fetched 2026-11-19. https://github.com/solioanalytics/open-fpl-solver
- [S2] open-fpl-solver README and commit log. https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/README.md, https://github.com/solioanalytics/open-fpl-solver/commits
- [S3] open-fpl-solver settings docs and defaults. https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/data/README.md, https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/data/comprehensive_settings.json, https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/data/user_settings.json
- [S4] open-fpl-solver source: `dev/solver.py` (highspy model, captain, bench, chips, objective, randomisation, public team rebuild), `dev/data_parser.py` (CSV formats), `data/getting_team_json.md`. https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/dev/solver.py, https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/dev/data_parser.py, https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/data/getting_team_json.md
- [S5] AIrsenal README, releases and commits. https://github.com/alan-turing-institute/AIrsenal, https://github.com/alan-turing-institute/AIrsenal/releases
- [S6] AIrsenal docs: how-it-works, xg-models (MAE/RMSE tables), adding-a-model. https://github.com/alan-turing-institute/AIrsenal/blob/main/docs/how-it-works.md, https://github.com/alan-turing-institute/AIrsenal/blob/main/docs/xg-models.md, https://github.com/alan-turing-institute/AIrsenal/blob/main/docs/adding-a-model.md
- [S7] OpenFPL repo (README, licence, commits). https://github.com/daniegr/OpenFPL
- [S8] Groos, "OpenFPL: An open-source forecasting method rivaling state-of-the-art Fantasy Premier League services", arXiv 2508.09992 v1 (29 Jul 2025), CC BY 4.0. https://arxiv.org/abs/2508.09992, https://arxiv.org/html/2508.09992v1
- [S9] OpenFPL issue #5 and author reply. https://github.com/daniegr/OpenFPL/issues/5
- [S10] vaastav/Fantasy-Premier-League LICENSE (MIT, plus a note that the data belongs to FPL and Understat). https://github.com/vaastav/Fantasy-Premier-League/blob/master/LICENSE
- [S11] HiGHS repo (MIT). https://github.com/ERGO-Code/HiGHS
- [S12] PyPI JSON for highspy, pulp, ortools, jaxlib (versions, licences, wheels). https://pypi.org/project/highspy/, https://pypi.org/project/pulp/, https://pypi.org/project/ortools/, https://pypi.org/project/jaxlib/
- [S13] PuLP README ("CBC is not shipped inside the PuLP package"). https://github.com/coin-or/pulp
- [S14] COIN-OR CBC LICENSE (EPL-2.0). https://github.com/coin-or/Cbc/blob/master/LICENSE
- [S15] OR-Tools repo and releases. https://github.com/google/or-tools/releases
- [S16] pyproject files: open-fpl-solver (`requires-python >=3.14`, `highspy>=1.11.0`) and AIrsenal (jax, numpyro, deap, bpl-next). https://github.com/solioanalytics/open-fpl-solver/blob/HEAD/pyproject.toml, https://github.com/alan-turing-institute/AIrsenal/blob/main/pyproject.toml
- [S17] Licences via the GitHub API: DEAP (LGPL-3.0) https://github.com/DEAP/deap ; bpl-next (MIT) https://github.com/anguswilliams91/bpl-next ; KBestSearch (Apache-2.0) https://github.com/daniegr/KBestSearch
- [S18] AIrsenal `tree_search.py` docstring ("enumerate every legal move for every gameweek"). https://github.com/alan-turing-institute/AIrsenal/blob/main/src/airsenal/optimization/transfer_optimizers/tree_search.py
- [S19] FPL Review docs, xMins. https://docs.fplreview.com/the-model/projections/xmins ; [S19b] Free model: https://docs.fplreview.com/the-model/projections/free-model/ ; [S19c] Premium features: https://docs.fplreview.com/getting-started/premium-features
- [S20] FPL API `bootstrap-static` (fields `ep_next`, `ep_this`, `defensive_contribution`, `expected_*`; events; chips), fetched 2026-11-19. https://fantasy.premierleague.com/api/bootstrap-static/
- [S21] Premier League, "All you need to know about changes to FPL for 2025/26" (defensive contributions). https://www.premierleague.com/news/4362211
- [S22] 2026/27 rule changes (secondary sources: BPS update, AM chip gone, two Chip sets). https://www.fantasyfootballscout.co.uk/2026/07/20/fpl-2026-27-5-rule-changes-new-features-announced, https://www.rotowire.com/soccer/article/fpl-2026-27-rule-changes-player-prices-and-position-changes-explained-124721
- [S23] Transfer Algorithm (Tor Mikkel Tokvam) Patreon. https://www.patreon.com/TransferAlgorithm/posts/building-blocks-20740418
- [S24] penaltyblog README and repo metadata. https://github.com/martineastwood/penaltyblog
- [S25] elcaiseri/OpenFPL-Scout-AI README. https://github.com/elcaiseri/OpenFPL-Scout-AI
- [S26] open-fpl-solver PR #49, the move to highspy. https://github.com/sertalpbilal/FPL-Optimization-Tools/pull/49
