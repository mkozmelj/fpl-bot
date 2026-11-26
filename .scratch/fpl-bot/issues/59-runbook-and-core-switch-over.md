# 59: Runbook and Core switch-over checklist

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the owner documentation Phase 2 needs to go live, and the one PR that turns the Core model on.
- `docs/runbook-secrets.md`: setting `ANTHROPIC_API_KEY` as a sealed Railway variable, setting a hard monthly spend limit in the Anthropic Console, and what the in-app ceiling does.
- Runbook section on running `python -m fplbot backtest` locally and reading its report.
- A Core switch-over checklist: backtest report pasted into the PR, bar met in both seasons, the model setting changed from `Baseline` to `Core`, and a check after deploy that `/status` and advice headers say Core.
- A Claude-overrides checklist: `/accuracy scout` bar met, then `claude_overrides_live` turned on.
- Update `core/README.md` for the new modules, commands and jobs, and `GLOSSARY.md` if any new term appeared.

**Blocked by:** 48: Backtest CLI; 55: Claude adapter, guardrails and `/why`; 57: `/note`: a Member's own team news

**Status:** open

- [ ] The runbook covers the key, the Console limit, the backtest and both checklists.
- [ ] `core/README.md` lists `prediction`, `explain`, the new jobs and commands.
- [ ] If the backtest bar is met, the switch-over PR is opened with the report; if not, the ticket records the result and advice stays on Baseline.
