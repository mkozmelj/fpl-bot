# Operations: monitoring, alerts, migrations and season rollover

Type: grilling
Status: resolved
Assignee: owner
Blocked by: —

## Question

Given [Architecture, frameworks and hosting for v1](12-architecture-and-framework.md), how is the bot operated? Decide worker liveness (Railway health checks are HTTP-only, so for example an external heartbeat), failure alerts to the owner, database migrations on deploy, backups, and season rollover. Ingestion's job log and 403 alerts are already set in [Which data the bot collects, how often, and what it keeps](13-data-ingestion-design.md).

## Answer

Resolved by grilling with the owner, 2026-11-23.

- **Liveness:** the bot sends a heartbeat ping every 5 minutes to the URL in an optional `HEARTBEAT_URL` variable, and only while its event loop and scheduler are healthy. The ping never touches the DB, so it doesn't wake Neon, and it carries no Member data. The owner's own shared monitoring service does the checking and alerting for a dead bot, outside this repo, so there is no Healthchecks.io account here.
- **Owner alerts:** one in-process `notify_owner()` Telegram DM, covering job failures, 403s, stale-data failures and a failed migration. Alerts are deduplicated per job and failure type: one DM, then at most one reminder every 6 hours, and a "recovered" DM when it's fixed. Each carries a short fixed code, never a stack trace or Member details. Alerts about a dead bot are out of scope, because external monitoring covers them.
- **Migrations:**
  - **Where:** Railway's pre-deploy command runs `alembic upgrade head` from the signed image, in a short-lived container with the service's own variables. The DB URL stays in Railway sealed variables and never reaches CI, which keeps the rule from [Security and secret handling for a public open-source repo](16-security-and-open-source-hygiene.md) that the Railway project token is the only CI secret.
  - **Failure:** a failed migration aborts the deploy and the old container keeps running.
  - **Fallback:** if pre-deploy doesn't fit an image-based service, the container runs `alembic upgrade head` at startup under a Postgres advisory lock, before the scheduler and the Telegram poller start. **To verify against Railway's docs when the pipeline is built.**
  - **Compatibility:** migrations are backward-compatible with the previous image (expand then contract), because a rollback runs the old image against the new schema. A CI check rejects drop or rename operations unless the migration is labelled as a contract step. See [ADR 0003](../../../docs/adr/0003-migrations-in-railway-pre-deploy.md).
- **Smoke check:** with no inbound HTTP, the bot logs `ready sha=<commit>` once migrations, the Telegram poll and the scheduler are up. CI reads the deployment logs with the Railway token and waits up to 5 minutes for that exact SHA, and rolls back if it doesn't appear. The bot also DMs the owner "online vX" after each deploy. No new secret.
- **Backups:** a nightly in-process export of only the Member and config tables (Members, invites, Watch lists, Goals). It is encrypted with `age` against a public key whose private key lives only in the owner's password manager, sent as a document to the owner's Telegram chat, and the last 7 are kept. The large tables (price snapshots, Elite aggregates) rely on Neon's short restore window and the backfill job. A restore drill goes in the runbook (decrypt, restore into an empty DB, check), and is done once before launch.
- **Season rollover:** the bot never rolls over by itself.
  1. It detects the new season (`bootstrap-static` shows GW1 and different IDs).
  2. It pauses alerts and advice.
  3. It DMs the owner a checklist.
  4. The owner runs an owner-only `/rollover`, which archives last season's aggregates under a season key, clears Rival picks and Followed leagues, and keeps Members (team ID, chat, timezone).
  5. Each Member is asked once to reconfirm their Goal and leagues.
  Every table has a `season` column from day one, so nothing needs a destructive reset.
- **`/status`:** owner-only and read-only, next to `/accuracy`. It shows uptime and deploy version, the last completion of each job (`price_archive`, `picks`, `elite`, `gw_final`), whether Neon is reachable, Neon storage, and Anthropic spend if a key is set.
- **Cost guards:**
  - Railway's usage limit and alert are set.
  - The Anthropic hard monthly limit already decided stays.
  - The owner gets a one-time DM when Neon storage passes 70%, or compute hours pass 80% of the month.
  - If reading Neon usage needs an API key, the automatic DM is skipped, `/status` shows only what it can read without one, and the runbook gets a monthly check in the Neon console.
- **Handed on:** `docs/runbook-secrets.md` gains the restore drill, the monthly Neon check and the `HEARTBEAT_URL` setting.
