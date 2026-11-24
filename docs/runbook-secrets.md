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
| `BACKUP_AGE_PUBLIC_KEY` (backup `age` public key, `age1...`) | Railway variable (public, not secret) | the nightly backup |
| `HEARTBEAT_URL` (optional, the uptime monitor's ping URL) | Railway sealed variable | the heartbeat |
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
- Settings → Environments: create `production`, deployment branches `main` only, and add the
  Railway project token as the environment secret `RAILWAY_TOKEN`. Then follow "Deploys" below.
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
2. GitHub → Settings → Environments → `production`: replace the `RAILWAY_TOKEN` secret.
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
2. Railway → Variables: set `BACKUP_AGE_PUBLIC_KEY` to the new public key (the `age1...` line
   `age-keygen` prints), deploy. A malformed key stops the bot at startup with a config error
   naming the variable.
3. Keep the old private key until the last backup made with it has rolled out of the owner chat
   (7 days), then delete it.

### Owner Telegram ID

Not secret, but it decides who may `/invite`. Change it only when the owner account changes:
Railway → Variables → `OWNER_TELEGRAM_ID`, deploy.

## Nightly Member backup

Every night at 04:00 UK time the bot exports the Member and config tables (`members`, with each
Member's Goal and settings; `invites`; `watch_list`) as SQL, encrypts it with `age` to
`BACKUP_AGE_PUBLIC_KEY` and sends it to the owner chat as `fplbot-members-<date>.sql.age`. The
caption gives the time taken and the Member count. The chat keeps the last 7: Telegram lets a
bot delete only messages under 48 hours old, so once 7 backup messages exist, each new backup
overwrites the message holding the oldest one (an edit, so no notification and it stays at that
message's place in the chat). The latest backup is the one whose caption has the latest date,
not necessarily the lowest in the chat. Deleting a backup message by hand is fine; the bot sends
a new message next time. Without `BACKUP_AGE_PUBLIC_KEY` the backup is skipped and the owner is
told once (again after the key has been set and removed).

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
6. Check: the Member count matches the backup's caption, and a known Member's Goal and Watch list
   are present.
7. Drop the scratch database and delete `members.sql`.

For a real restore into Neon, create a new Neon branch first, restore into it, point
`DATABASE_URL` at it, and let the backfill job rebuild the large tables (price snapshots, Elite
aggregates), which are not in the backup and rely on Neon's own short restore window.

## Monthly Neon check

The bot DMs the owner once when its database passes 70% of the storage limit (checked daily at
04:30 UK; `pg_database_size`, a little below what Neon bills). The limit is
`DATABASE_STORAGE_LIMIT_MB` (default 1024, Neon Free); set it if the plan changes. `/status` shows
the same size. Compute hours are readable only through the Neon API, which needs a key the bot
does not hold, so there is no automatic compute-hours DM: this monthly check covers it.

On the first weekend of each month, in the Neon console:

- **Storage** below 70% of the free 1 GB, and **compute hours** below 80% of the monthly 100.
  If either is close, check which tables grew (price snapshots, Rival picks) before the next
  Gameweek.
- **Restore window**: note the current point-in-time restore window; `PRIVACY.md` refers to it.
- The bot's role is the only role with access and the project has no unexpected branches.

Also glance at the Railway usage and its alert, and the Anthropic workspace spend once a key is set.

## `HEARTBEAT_URL`

The bot pings this URL (a plain `GET`) every 5 minutes while its event loop and scheduler are
healthy, starting when it logs `ready sha=`. The ping never touches the database and carries no
Member data. A failed ping is only logged (`heartbeat ping failed: <error type>`, never the URL);
the next one goes 5 minutes later. If the scheduler has died, the bot logs `heartbeat skipped`
and the monitor alerts.

1. In the owner's own monitoring service, create a check that expects a ping every 5 minutes with a
   grace period of about 10 minutes, and alerts the owner when pings stop.
2. Railway → Variables: set `HEARTBEAT_URL` to that check's ping URL (treat it as a secret, since
   anyone holding it can send fake pings), deploy.
3. Confirm the monitor shows pings within 10 minutes.

Unset `HEARTBEAT_URL` disables pings; forks normally leave it unset.

## Deploy version and the `ready sha=` line

At startup the bot checks the database is at the latest migration, starts the Telegram poll, the
scheduler and the heartbeat, then logs `ready sha=<commit>` and DMs the owner
`online v<version> (<short commit>)`. The commit comes from `GIT_SHA`, baked into the image at
build time (`--build-arg GIT_SHA=<commit>`); without it, Railway's `RAILWAY_GIT_COMMIT_SHA` (set
only for deploys triggered from GitHub, not image deploys); otherwise `unknown`. If the database
is behind, the bot logs `startup aborted: the database is not at the latest migration` and exits,
so the smoke check never sees `ready` and the deploy rolls back. `/status` shows the same version
and the uptime.

A database *ahead* of the image (a rollback after a migration) is accepted: migrations are
expand-only, so the previous image runs on the newer schema, and its `fplbot migrate` leaves that
database alone (`the database is ahead of this image (a rollback?): nothing to migrate`).

## Deploys

Every merge to `main` runs `.github/workflows/deploy.yml`; there is no other way to deploy.

1. **Image job:** builds the root `Dockerfile` once (`GIT_SHA` = the commit), scans it with Trivy
   (fails on fixable HIGH/CRITICAL), pushes `ghcr.io/<owner>/<repo>:sha-<commit>`, signs that
   digest keylessly with cosign and attests its build provenance.
2. **Deploy job** (environment `production`): verifies the cosign signature (signed by this
   workflow on `main`) and the provenance attestation, records the deployment now serving, points
   the `production` tag at the verified digest, runs `railway redeploy` (Railway re-pulls the tag),
   and waits up to 5 minutes for `ready sha=<commit>` in the new deployment's logs. If it doesn't
   appear, it puts the `production` tag back on the previous digest and rolls Railway back to the
   previous deployment (skipped when the new one failed before going live, e.g. a failed
   migration, because the old container never stopped). A failed or rolled-back deploy leaves the
   run red; fix forward with a new PR.

### Migrations: Railway's pre-deploy command

Chosen path: Railway's **pre-deploy command** `fplbot migrate` (`alembic upgrade head`), run from
the image being deployed. No advisory-lock fallback is needed. Checked against Railway's docs on
24 Nov 2026:

- [Pre-deploy command](https://docs.railway.com/deployments/pre-deploy-command): runs between
  build and deploy "in a separate container", with the service's variables and private network,
  using what is "installed in the application image"; a non-zero exit means "the deployment will
  not proceed" (not retried). No time limit unless the Pre-deploy Timeout is set.
- [Deployments reference](https://docs.railway.com/deployments/reference): "If the source is a
  Docker Image, the build step is skipped", so pre-deploy runs straight from the pulled image.
- [Deployment teardown](https://docs.railway.com/deployments/deployment-teardown): "Once the new
  deployment is active, the previous deployment is sent a SIGTERM", so after a failed migration
  the old container keeps running.
- [Infrastructure as code reference](https://docs.railway.com/infrastructure-as-code/reference):
  `preDeploy` is a per-service deploy setting next to an image `source`.
- [Deploy from a container registry](https://railway.com/guides/private-container-registry):
  with a mutable tag, "The redeploy pulls the tag again and picks up the new digest".

No page shows an image-sourced service *with* a pre-deploy command in one example, so confirm it
on the first deploy: the deployment's logs show the Alembic lines before the bot starts. If
pre-deploy were ever skipped, the bot refuses to start against a database behind it (no `ready`
line), so the smoke check rolls back instead of running on an old schema.

### One-time Railway and GitHub setup

1. Railway (project in EU West): create the service from a **Docker image**,
   `ghcr.io/<owner>/<repo>:production` (lowercase).
   - Settings → Deploy: **Pre-deploy command** `fplbot migrate`, **Pre-deploy Timeout** 300 s
     (a hung migration then fails the deploy instead of holding it); start command empty (the
     image's `fplbot`); no healthcheck (no HTTP); restart policy On Failure.
   - **Image auto-updates off** (only CI moves the `production` tag; an auto-update would race it).
   - Variables: the sealed ones in "Where each secret lives". Set
     `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=0` so two bots don't long-poll Telegram at once.
   - Project → Settings → Tokens: a **project token** for the production environment.
2. GitHub: the `production` environment with `RAILWAY_TOKEN` (above), and the repository
   **variable** `RAILWAY_SERVICE_ID` (the service's ID, not secret). The deploy workflow runs only
   where that variable is set, so forks never try to deploy.
3. First run: merge to `main`. The first push creates the GHCR package as **private**; set it to
   **public** (Package settings → Change visibility; Railway Hobby pulls public images only), then
   re-run the failed deploy job. There is no earlier deployment to roll back to on this run.
4. Check the deployment logs show the Alembic lines (pre-deploy ran) and `ready sha=<commit>`,
   and the owner got `online v…`.

### Verify an image by hand

```sh
cosign verify ghcr.io/<owner>/<repo>@sha256:<digest> \
  --certificate-identity https://github.com/<owner>/<repo>/.github/workflows/deploy.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/<owner>/<repo>@sha256:<digest> --repo <owner>/<repo>
```

### Pinned tools

The workflow pins Trivy, the Railway CLI and cosign by version (Trivy and the CLI also by the
SHA-256 of the release archive) in its `env:` block. Dependabot doesn't see those, so bump them by
hand now and then, taking each archive's SHA-256 from the release's asset digest.
