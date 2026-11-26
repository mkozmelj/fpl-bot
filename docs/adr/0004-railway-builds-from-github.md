# Railway builds and deploys from the GitHub repo, after CI

Supersedes the deploy part of ADR 0001 and the "signed image" wording of ADR 0003.

Railway's service is connected to this repository's `main` branch. On every push to `main` it builds the repo-root `Dockerfile` itself, waits for GitHub Actions to finish on that commit ("Wait for CI"), runs `fplbot migrate` as the pre-deploy command, and starts the new container. The GHCR image, cosign signature, provenance attestation and the scripted redeploy, smoke check and rollback of ticket 42 are retired.

ADR 0001 rejected Railway's GitHub autodeploy for two reasons, and both have since changed:

- **Skipped workflows get through "Wait for CI".** `main` is now protected: every change arrives through a pull request whose nine required checks (lint and types, migrations, tests, Gitleaks, pip-audit, workflow lint, both CodeQL analyses, and the image scan) must pass before merge. "Wait for CI" is a second gate, not the only one.
- **The Railway GitHub App needs broader permissions.** The app is installed on this one repository, which is public, so read access exposes nothing that isn't already public. In exchange, CI holds no secret at all: the Railway project token is gone.

For a bot serving 5–10 invited friends, the signed-image pipeline protected against tampering with a registry that this setup no longer has, at the cost of a public GHCR package, a CI secret and about 200 lines of workflow and script to maintain.

## Consequences

- The vulnerability scan moves to CI: the `Image scan` job builds the same `Dockerfile` and fails on fixable HIGH/CRITICAL findings (Trivy) on every pull request and push to `main`. Railway's build is not scanned again, but it builds the same pinned base images and locked dependencies.
- Migrations still run in Railway's pre-deploy command (ADR 0003): a failed migration aborts the deploy and the old container keeps running. CI still never holds the database URL.
- There is no automatic rollback. If a deploy starts but the bot misbehaves, the owner rolls back in Railway's UI (Deployments → the previous one → Redeploy). A database behind the image still stops the bot before `ready sha=`.
- The deployed commit comes from Railway's `RAILWAY_GIT_COMMIT_SHA`, which Railway sets for deploys triggered from GitHub; the image no longer bakes in a `GIT_SHA`.
- Railway's config-as-code file (`railway.json`) is deprecated, so the service settings live in Railway's UI and are listed in `docs/runbook-secrets.md`, "Deploys".
