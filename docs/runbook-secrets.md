# Runbook: secrets, restore drill and routine checks

Owner-only procedures for the production instance. Decisions behind them: tickets 16 and 23 in
`.scratch/fpl-bot/issues/`, ADR 0003. Nothing here needs a secret to be written down anywhere but
Railway, the GitHub Environment and the owner's password manager.

## Where each secret lives

| Secret | Lives in | Used by |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Railway sealed variable | the bot |
| `DATABASE_URL` (Neon pooled URL) | Railway sealed variable | the bot, the pre-deploy migration |
| `OWNER_TELEGRAM_ID` | Railway sealed variable (not secret, kept with the others) | the bot |
| `ANTHROPIC_API_KEY` (optional, not used in Phase 1) | Railway sealed variable | the bot |
| Backup `age` public key | Railway variable (public, not secret) | the nightly backup |
| Backup `age` private key | owner's password manager only | the restore drill |
| Railway project token (production environment) | GitHub Environment `production`, restricted to `main` | the deploy job; the **only** CI secret |

CI tests use a throwaway Postgres container and GHCR pushes use `GITHUB_TOKEN`; neither needs a
stored secret. Local development uses a gitignored `.env` (see `.env.example`).

## One-time repository setup (after the first push)

- Settings → Code security: enable **secret scanning** with **push protection**, **private
  vulnerability reporting**, Dependabot alerts and security updates.
- Settings → Branches: protect `main`; require a PR and these checks: `Lint and types`,
  `Migrations are expand-only`, `Tests`, `Gitleaks`, `pip-audit`, `actionlint and zizmor`,
  `Analyze (python)`, `Analyze (actions)`. No required commit signing.
- Settings → Actions → General: workflow permissions **read-only** by default; do not allow Actions
  to create or approve PRs.
- Settings → Environments: create `production`, deployment branches `main` only, add the Railway
  project token (ticket 42).
- Locally: `uvx pre-commit install` for the gitleaks pre-commit hook.

## Rotating a secret

Rotate immediately if a secret may have leaked (gitleaks finding, push-protection alert, a log
line, a lost device), otherwise whenever convenient. After each rotation, check the bot logs a
fresh `ready sha=` line and answers `/status`.

### Telegram bot token

1. In Telegram, open @BotFather → `/mybots` → the bot → **API Token** → **Revoke current token**.
   The old token stops working at once, so the bot goes offline until step 2.
2. Railway → service → Variables: replace `TELEGRAM_BOT_TOKEN`, keep it sealed, deploy.
3. Check `/status` from the owner chat.

### Neon database password (`DATABASE_URL`)

1. Neon console → project → **Roles** → the bot's role → **Reset password**.
2. Copy the new **pooled** connection string (host contains `-pooler`).
3. Railway → Variables: replace `DATABASE_URL`, keep it sealed, deploy. The pre-deploy migration
   uses the same variable, so a wrong value aborts the deploy and the old container keeps running.
4. Check `/status` shows Neon reachable.

### Railway project token

1. Railway → project → Settings → Tokens: create a new token scoped to the **production**
   environment.
2. GitHub → Settings → Environments → `production`: replace the token secret.
3. Delete the old token in Railway.
4. Re-run the latest deploy workflow on `main` (or merge a trivial PR) and check it reaches the
   smoke check.

### Anthropic API key (once used)

1. Anthropic Console → the bot's dedicated workspace → API keys: create a new key, then disable and
   delete the old one.
2. Railway → Variables: replace `ANTHROPIC_API_KEY`, sealed, deploy.
3. Confirm the workspace's hard monthly spend limit is still set.

### Backup `age` key pair

1. `age-keygen -o backup.key` on a trusted machine; store the private key in the password manager,
   then delete the file.
2. Railway → Variables: replace the backup public key, deploy.
3. Keep the old private key until the last backup made with it has rolled out of the owner chat
   (7 days), then delete it.

### Owner Telegram ID

Not secret, but it decides who may `/invite`. Change it only when the owner account changes:
Railway → Variables → `OWNER_TELEGRAM_ID`, deploy.

## Restore drill

Do this once before launch and after any change to the backup format. Use a scratch database,
never production.

1. In the owner chat, download the latest backup document the bot sent.
2. Decrypt it with the private key from the password manager:
   `age --decrypt -i backup.key -o members.sql <backup file>`; delete `backup.key` afterwards.
3. Start an empty database: `docker compose up -d` and
   `createdb -h localhost -U postgres fplbot_restore`.
4. Migrate it to the schema the backup came from:
   `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fplbot_restore uv run python -m fplbot migrate`
   (from `core/`).
5. Load the export: `psql -h localhost -U postgres -d fplbot_restore -f members.sql`.
6. Check: the Member count matches `/status`, and a known Member's Goal and Watch list are present.
7. Drop the scratch database and delete `members.sql`.

For a real restore into Neon, create a new Neon branch first, restore into it, point
`DATABASE_URL` at it, and let the backfill job rebuild the large tables (price snapshots, Elite
aggregates), which are not in the backup and rely on Neon's own short restore window.

## Monthly Neon check

On the first weekend of each month, in the Neon console:

- **Storage** below 70% of the free 1 GB, and **compute hours** below 80% of the monthly 100.
  If either is close, check which tables grew (price snapshots, Rival picks) before the next
  Gameweek.
- **Restore window**: note the current point-in-time restore window; `PRIVACY.md` refers to it.
- The bot's role is the only role with access and the project has no unexpected branches.

Also glance at the Railway usage and its alert, and the Anthropic workspace spend once a key is set.

## `HEARTBEAT_URL`

The bot pings this URL every 5 minutes while its event loop and scheduler are healthy. The ping
never touches the database and carries no Member data.

1. In the owner's own monitoring service, create a check that expects a ping every 5 minutes with a
   grace period of about 10 minutes, and alerts the owner when pings stop.
2. Railway → Variables: set `HEARTBEAT_URL` to that check's ping URL (treat it as a secret, since
   anyone holding it can send fake pings), deploy.
3. Confirm the monitor shows pings within 10 minutes.

Unset `HEARTBEAT_URL` disables pings; forks normally leave it unset.
