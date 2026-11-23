# Run database migrations in Railway's pre-deploy command, never from CI

`alembic upgrade head` runs in Railway's pre-deploy command, from the same signed image that is about to be deployed, using the service's own sealed variables. CI never holds the Neon URL, so the Railway project token stays the only CI secret. In a public repo that keeps a CI compromise from reaching Member data (Telegram chat IDs and team IDs). If a migration fails, the deploy is aborted and the old container keeps running. If Railway's pre-deploy command turns out not to fit an image-based service, the fallback is to migrate at container start under a Postgres advisory lock, before the scheduler and Telegram poller start. Verify this when the pipeline is built.

## Consequences

- Migrations must be backward-compatible with the previous image (expand then contract), because a rollback runs the old image against the new schema. A CI check rejects drop or rename operations unless the migration is labelled as a contract step.
- Migrations are tested in CI against a throwaway Postgres container only, so there is no DB secret in CI.
- The smoke check is a `ready sha=<commit>` log line, read with the Railway token.
