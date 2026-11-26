# Run database migrations in Railway's pre-deploy command, never from CI

`alembic upgrade head` runs in Railway's pre-deploy command, from the same signed image that is about to be deployed, using the service's own sealed variables. CI never holds the Neon URL, so the Railway project token stays the only CI secret. In a public repo that keeps a CI compromise from reaching Member data (Telegram chat IDs and team IDs). If a migration fails, the deploy is aborted and the old container keeps running. If Railway's pre-deploy command turns out not to fit an image-based service, the fallback is to migrate at container start under a Postgres advisory lock, before the scheduler and Telegram poller start. Verify this when the pipeline is built.

Verified against Railway's docs when the pipeline was built (ticket 42, 24 Nov 2026): pre-deploy fits an image-based service, so the advisory-lock fallback isn't used. The pages that confirmed it are listed in `docs/runbook-secrets.md`, "Deploys".

Amended by ADR 0004 (26 Nov 2026): Railway now builds the image from the GitHub repo itself, so the pre-deploy command runs from Railway's own build of the commit being deployed rather than from a signed GHCR image, and CI holds no secret at all (the Railway project token is gone). Everything else here still holds.

## Consequences

- Migrations must be backward-compatible with the previous image (expand then contract), because a rollback runs the old image against the new schema. The bot's startup check and `fplbot migrate` therefore accept a database ahead of the image. A CI check rejects drop or rename operations unless the migration is labelled as a contract step.
- Migrations are tested in CI against a throwaway Postgres container only, so there is no DB secret in CI.
- The bot logs `ready sha=<commit>` once it is up; since ADR 0004 the owner checks it in Railway's deployment logs (there is no scripted smoke check).
