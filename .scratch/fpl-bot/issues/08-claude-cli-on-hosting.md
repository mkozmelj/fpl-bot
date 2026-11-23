# Can Claude run on a host using a subscription, and what does the API cost otherwise?

Type: research
Status: resolved
Blocked by: —

## Question

Can the bot use the owner's **Claude subscription** (Pro/Max) instead of paid API tokens when it runs on a hosting platform?

Cover:
- Can Claude Code run headless (`claude -p`, the Agent SDK) on a server or in a container, using a long-lived subscription token (for example `claude setup-token`), not interactive login?
- Do Anthropic's consumer terms and usage policy allow this for an automated job? Do they allow it when the output serves 5–10 other people?
- Are there scheduled or cloud options within the subscription itself (for example Claude Code routines or scheduled agents)?
- Fallback: estimated monthly API cost for this workload with the cheapest suitable current model, prompt caching and the Batch API. Assume one Scout run per Gameweek plus short per-Member summaries.

Use only Anthropic's official docs and terms. Findings go in `.scratch/fpl-bot/research/08-claude-cli-on-hosting.md`.

## Answer

- **Technically yes.** `claude setup-token` gives a one-year OAuth token. Set as `CLAUDE_CODE_OAUTH_TOKEN`, it runs `claude -p` and the Agent SDK headless on any host against the owner's Pro/Max limits. Caveats: those limits are shared with the owner's own use, and `--bare` (slated to become the `-p` default) ignores the token.
- **Automating it for the owner's own use is explicitly allowed.** The docs say the token is for "CI pipelines and scripts", and they publish a cron GitHub Actions example that uses the subscription token.
- **Serving 5–10 Members from the subscription is not explicitly allowed and sits close to explicit bans.** Builders "should use API key authentication". Routing requests through Pro/Max credentials "on behalf of their users" is not permitted. The Consumer Terms forbid making the account "available to anyone else" and require non-commercial use. Anthropic may enforce without notice.
- **There are subscription-native schedulers:** cloud scheduled tasks (formerly routines; Pro and up; at most hourly; research preview) and GitHub Actions cron with `claude_code_oauth_token`. Both draw normal subscription usage.
- **The API fallback is trivial in cost.** On Claude Haiku 5.5 it is about $1.10 a season at list price and about $0.50 with caching and Batch (about 4.75M in / 1.25M out tokens for 38 Gameweeks × 1 Scout run + 10 Member summaries). Sonnet 5.5 is about $9–22 and Opus 5.5 about $19–44 a season.
- **Max/Ultra plans include $100/$200 a month of API credits** (Pro gets none). They cover the Messages and Batches APIs and the Agent SDK with an API key, so this workload costs nothing extra.
- **Recommendation:** run the hosted bot on an API key (Commercial Terms, which allow serving end users), paid from Max credits if available. Keep the subscription for the owner's own dev work. Never send Member text to a subscription-backed Claude.

Findings: [../research/08-claude-cli-on-hosting.md](../research/08-claude-cli-on-hosting.md)

## Comments

- 2026-11-19, owner fact: the owner is on **Claude Pro**, which has no included API credits. So the hosted bot uses its own Anthropic API key on the cheapest suitable model, about $0.50–1.10 a season, and the owner's subscription is used only for development and the owner's own personal jobs, never for anything Members see.
