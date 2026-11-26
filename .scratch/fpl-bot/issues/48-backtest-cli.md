# 48: Backtest CLI

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** `python -m fplbot backtest`, the owner's and contributors' tool for deciding whether the Core model may ship.
- Downloads vaastav per-Gameweek history for 2024/25 and 2025/26 and the matching football-data.co.uk season CSVs into a git-ignored local cache at run time. Never committed, never fetched in CI.
- Walk-forward: the prediction for Gameweek k uses only data available before Gameweek k's deadline. Settings are tuned on 2024/25 only; 2025/26 is the untouched check.
- Compares the Core model with `ep_next` (vaastav's per-Gameweek FPL expected points) and the last-5 average on MAE and Spearman rank correlation, over Footballers with at least one appearance in the window. Secondary view: 0-2 versus 3+ point buckets. Reports horizons 3, 5 and 8.
- Also reports the captain and bench settings (0.3 tie band, 0.85 start-probability floor, σ prior 15, 10% differential allowance) at their defaults and at a small grid around them.
- Writes a Markdown report with a clear "bar met / not met" line per season, for the Core switch-over PR.

**Blocked by:** 47: Expected-points model (pure) and the Baseline

**Status:** open

- [ ] CI runs the CLI on a tiny synthetic season fixture and checks the report format, with no network.
- [ ] A leakage test proves no data after a Gameweek's deadline reaches that Gameweek's prediction.
- [ ] The cache directory is in `.gitignore`, and gitleaks or a CI check fails if CSVs are added to the repo.
- [ ] The report states the bar per season: beat `ep_next` on both MAE and rank correlation.
- [ ] The run needs no secrets.
