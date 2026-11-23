# Security and secret handling for a public open-source repo

Type: grilling
Status: resolved
Assignee: owner
Blocked by: 12

## Question

For a fully public repo, decide:
- where each secret lives (Telegram token, Anthropic API key, Neon DB URL, Railway project token)
- secret scanning: GitHub push protection, a gitleaks pre-commit hook, and CI scanning
- dependency and supply-chain checks (Dependabot or pip-audit, pinned and hashed dependencies)
- which tools fill the CI pipeline's security gates (decided shape: PR checks → build one image → scan and sign that image → public GHCR → `railway redeploy` with an environment-scoped project token → smoke check and rollback): secret scanning, CodeQL or similar, dependency audit, image scan, signing and provenance, GitHub Actions pinned by SHA and workflow linting
- Railway variables (sealed) for runtime secrets, the GitHub Environment holding the Railway project token, and the Anthropic Console spend limit
- the bot allow-list (no webhook: v1 uses Telegram long polling, so a webhook secret token is not needed)
- what Member data we store (FPL team ID, Telegram chat ID, Watch list, timezone) and how a Member deletes it
- a `.env.example` with placeholders only
- the licence choice (for example MIT or AGPL), compatible with the solver module derived from Apache-2.0 open-fpl-solver (see ADR 0002)
- `SECURITY.md`
- how forks run their own instance without our secrets

## Answer

Resolved by grilling with the owner, 2026-11-19. The owner accepted every recommendation.

- **Licence:** Apache-2.0 for the whole repo, with a `NOTICE` crediting open-fpl-solver. It matches the upstream licence and adds a patent grant. AGPL was rejected: no gain for a non-commercial, invite-only bot, and it adds friction for forks.
- **Secrets:**
  - The Telegram token, Anthropic API key, Neon pooled URL and the owner's Telegram ID live only in **Railway sealed variables** (production).
  - The Railway project token is the **only** CI secret. It sits in a GitHub Environment `production` restricted to `main`. Tests use a throwaway Postgres container, and GHCR pushes use `GITHUB_TOKEN`.
  - Local dev uses a gitignored `.env`.
  - The Anthropic key is dedicated to this bot, in its own Console workspace with the hard monthly spend limit.
- **Secret scanning:** GitHub secret scanning with push protection, a gitleaks pre-commit hook, and gitleaks as a required PR check (diff on PRs, full history weekly).
- **Dependencies:** `uv.lock` with hashes (`--frozen --require-hashes`). Dependabot for `uv`, `github-actions` and `docker`, grouped weekly. `pip-audit` as a required PR check and a nightly run. Dependabot PRs are merged by hand, never auto-merged.
- **CI gates:** CodeQL (Python and Actions workflows), Trivy image scan (fail on fixable HIGH/CRITICAL), cosign keyless signing plus build-provenance attestation on the image digest, Actions pinned by full SHA, actionlint and zizmor, `permissions: {}` by default with per-job grants. The deploy job verifies the signature before `railway redeploy`. No SBOM or SLSA claims in v1.
- **Member data:** stored are the FPL team ID, Telegram chat ID, Goal, league ID, Watch list, timezone and alert time, and hashed invite codes. `/leave` hard-deletes everything. Logs carry an internal Member number only. Prompts to Claude carry no Member identifiers or team names. `PRIVACY.md` lists this and notes Neon's short restore window.
- **Unknown chats:** silent. Only allow-listed private chats get replies; groups are ignored. Invite codes expire after 48 hours, have at least 64 bits of randomness, and wrong attempts are rate-limited per chat.
- **`SECURITY.md` and forks:** GitHub private vulnerability reporting, best-effort, no bounty. `.env.example` has placeholders only. A fork needs `TELEGRAM_BOT_TOKEN` and `DATABASE_URL`, with an optional `ANTHROPIC_API_KEY`, and gets a `docker-compose` Postgres. The deploy job runs only in the owner's repo. `main` is protected with no required commit signing.
- **Prompt injection (Scout notes):** Claude gets no tools and no network. Notes are length-capped and wrapped as quoted data. Output is parsed against a strict schema (Footballer ID, minutes change, short reason) and dropped if it doesn't parse.
- **Runbook:** `docs/runbook-secrets.md` with a manual rotation checklist per secret (BotFather, Anthropic Console, Neon, Railway token).

No ADR: the licence is the only hard-to-reverse choice, and it isn't surprising given the Apache-2.0 solver.
