# 41: CI gates and open-source hygiene

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** every PR is checked automatically, and the public repo has what a fork needs (tickets 12, 16, 23). Decisions come from those tickets.
- GitHub Actions on PRs: ruff, pyright, the test suite against a throwaway Postgres service container (no DB secrets), gitleaks (diff on PRs, full history weekly), CodeQL (Python and Actions), `pip-audit` (also nightly), actionlint and zizmor. Every Action pinned by full SHA, `permissions: {}` by default with per-job grants.
- A check that rejects drop or rename operations in a migration unless it is labelled as a contract step (ADR 0003).
- Dependabot for `uv`, `github-actions` and `docker`, grouped weekly; merged by hand.
- A gitleaks pre-commit hook.
- `LICENSE` (Apache-2.0), `NOTICE` crediting open-fpl-solver, `SECURITY.md` (private vulnerability reporting, best effort), `PRIVACY.md` (what is stored, `/leave`, Neon's restore window), `.env.example` with placeholders only, a docker-compose Postgres for forks, and a secrets runbook with per-secret rotation, the restore drill, the monthly Neon check and the `HEARTBEAT_URL` setting.

Note: the repo has no git remote yet, so workflows can be written and linted locally (actionlint, zizmor) but not run until the repo is pushed.

**Blocked by:** 26: Walking skeleton: invite and redeem

**Status:** ready-for-agent

- [ ] Workflows exist for every gate above and pass actionlint and zizmor locally.
- [ ] The migration check fails on a sample drop-column migration and passes when it is labelled as a contract step.
- [ ] A fork can follow the README with `.env.example` and docker-compose to run the bot and the tests with no owner secrets.
- [ ] The listed docs exist and match tickets 16 and 23.
