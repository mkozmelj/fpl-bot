# FPL bot

An invite-only Telegram bot that gives a small group of Fantasy Premier League managers advice from
public FPL data: nightly Price alerts, and how their Squad differs from top-ranked managers and
their Rivals. Vocabulary: [GLOSSARY.md](GLOSSARY.md). Decisions: [docs/adr/](docs/adr/).

## Layout

- `core/`: the Python bot (package `fplbot`). Developer guide: [core/README.md](core/README.md).
- `docs/`: ADRs and the [secrets runbook](docs/runbook-secrets.md).
- `.github/`: CI gates and Dependabot.

## Run your own instance

You need Docker, [uv](https://docs.astral.sh/uv/) and your own bot token from @BotFather. None of
the owner's secrets are needed.

```sh
cp .env.example .env              # then put your bot token and Telegram user ID in it
docker compose up -d              # local Postgres 17 on localhost:5432
set -a; . ./.env; set +a
cd core
uv sync
uv run python -m fplbot migrate   # create the schema
uv run python -m fplbot           # start the bot (Ctrl-C to stop)
uv run pytest                     # the tests use TEST_DATABASE_URL from .env
```

`FPL_SOURCE=fake` (the default in `.env.example`) serves synthetic fixtures instead of calling the
FPL API.

## Contributing

Every change goes through a PR. CI runs ruff, pyright, the tests against a throwaway Postgres,
the migration expand/contract check, gitleaks, CodeQL, pip-audit, actionlint and zizmor. Install
the gitleaks pre-commit hook with `uvx pre-commit install`.

## Licence, privacy and security

Apache-2.0: see [LICENSE](LICENSE) and [NOTICE](NOTICE). What the bot stores and how to delete it:
[PRIVACY.md](PRIVACY.md). Reporting vulnerabilities: [SECURITY.md](SECURITY.md).
