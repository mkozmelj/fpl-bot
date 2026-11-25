# 42: Image, signing and Railway deploy

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a merge to `main` ships the bot with no manual step (tickets 12, 16, 23, ADR 0003).
- One Dockerfile building one image. CI builds it once, scans it with Trivy (fail on fixable HIGH/CRITICAL), signs it keylessly with cosign plus a build-provenance attestation, and pushes it to public GHCR with `GITHUB_TOKEN`.
- Railway's pre-deploy command runs `alembic upgrade head` from the signed image; a failed migration aborts the deploy and the old container keeps running. Verify this against Railway's docs; if pre-deploy doesn't fit an image-based service, fall back to running migrations at startup under a Postgres advisory lock, before the scheduler and poller start.
- The deploy job runs only in the owner's repo, in a GitHub Environment `production` restricted to `main`, holding the Railway project token as the only CI secret. It verifies the image signature, then `railway redeploy`.
- Smoke check: read deployment logs with the Railway token, wait up to 5 minutes for `ready sha=<this commit>` (ticket 38), and roll back if it doesn't appear.

Note: like ticket 41, this can't be run end to end until the repo is on GitHub and the Railway environment exists.

**Blocked by:** 38: `/status`, heartbeat and the `ready sha=` log line; 41: CI gates and open-source hygiene

**Status:** resolved

- [ ] The image builds locally and starts the bot against a local Postgres, logging `ready sha=`.
- [ ] The deploy workflow passes actionlint and zizmor and contains scan, sign, attest, verify, redeploy, smoke check and rollback steps in that order.
- [ ] The migration path (pre-deploy or advisory-lock fallback) is chosen with a note on which Railway docs confirmed it.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 177dc43; review fix-ups in 1004dd3). Tests live in `core/tests/`.
