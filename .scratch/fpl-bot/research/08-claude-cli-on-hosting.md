# Can Claude run on a host using a subscription, and what does the API cost otherwise?

Research for ticket `issues/08-claude-cli-on-hosting.md`. Researched 2026-11-19 against Anthropic's own docs, legal pages and Help Center only. Terms follow `GLOSSARY.md` (Member, Gameweek, Scout mode, Analyst mode, Price alert).

## TL;DR

- **It works technically.** `claude setup-token` mints a one-year OAuth token. Set as `CLAUDE_CODE_OAUTH_TOKEN`, it lets `claude -p` (and the Agent SDK, which runs the same binary) authenticate headless with the owner's Pro/Max plan on any server, container or CI runner. The docs present it as being "for CI pipelines and scripts".
- **Automating it for yourself is explicitly allowed.** Anthropic documents a cron-scheduled GitHub Actions workflow that authenticates with `claude_code_oauth_token`. Its Help Center says Agent SDK / `claude -p` runs on a plan login "draw from your subscription limits". This counts as the "explicitly permit" exception to the Consumer Terms' ban on bots and scripts.
- **Serving 5–10 other people from the owner's subscription is a grey area that leans towards not allowed.** The Claude Code legal page says people building products or services, "including those using the Agent SDK, should use API key authentication". It also says Anthropic does not permit routing requests "through Free, Pro, Max, or Ultra plan credentials on behalf of their users". The Consumer Terms also forbid making your account "available to anyone else" and require non-commercial use. Nothing names the case of a private, non-commercial bot whose *outputs* go to a few friends. The risk is enforcement "without prior notice" against the owner's personal account.
- **The risk is lower if Members never talk to Claude.** In Analyst mode, Claude only writes explanations of numbers that code computed, and Scout mode is one read per Gameweek. If no Member text ever reaches Claude, this looks much more like the owner's own use, with outputs shared "at your direction" (Consumer Terms §4). Sending Member free-text chat to a subscription-backed Claude is the clearest breach.
- **There are subscription-native scheduling options.** **Cloud scheduled tasks** (formerly *routines*) run Claude Code on Anthropic's cloud on a cron schedule, an API trigger or a GitHub event. They are available on Pro/Max/Ultra, draw normal subscription usage, can run at most once per hour, and are in research preview. **GitHub Actions cron** with the OAuth token is the other documented option.
- **The API fallback costs almost nothing.** The workload is 38 Gameweeks × (1 Scout run + 10 Member summaries), about 4.75M input and 1.25M output tokens a season. On **Claude Haiku 5.5** that is about **$1.10 per season** at list price and about **$0.50 per season** with caching and the Batch API (a few cents a month). Claude Sonnet 5.5 is about $9–22 per season and Claude Opus 5.5 about $19–44.
- **Max includes $100 a month of API credits.** The plan comes with $100/month in Claude Platform credits (Ultra $200; Pro gets none). They cover the Messages and Batches APIs and the Agent SDK *with an API key*, which pays for this workload many times over at no extra cost.
- **Recommendation:** run the hosted bot on an **API key under the Commercial Terms**, which explicitly allow powering "products and services Customer makes available to its own customers and end users". If the owner is on Max, link a Console org and pay with the included credits. Keep the subscription for the owner's own development work, and optionally for owner-only cloud scheduled tasks.

## 1. Technical feasibility

### Headless runs and long-lived subscription tokens

- `claude -p` runs Claude Code non-interactively and is the CLI form of the Agent SDK: "To run Claude Code in non-interactive mode, pass `-p` with your prompt" ([headless](https://code.claude.com/docs/en/headless)). It supports `--output-format json` and `--json-schema`, which fits the Scout mode's structured adjustments to minutes and Expected points.
- Long-lived token: "For CI pipelines, scripts, or other environments where interactive browser login isn't available, generate a one-year OAuth token with `claude setup-token`" ([authentication](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token)).
- Scope of the token: "This token authenticates with your Claude subscription and requires a Pro, Max, Ultra, Team, or Enterprise plan. It can only make model requests" (same page). Locally configured MCP servers still work. Remote Control and claude.ai connectors do not.
- Credential precedence puts `CLAUDE_CODE_OAUTH_TOKEN` below `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY` and `apiKeyHelper`. Any API key in the environment silently wins ([authentication precedence](https://code.claude.com/docs/en/authentication#authentication-precedence)).
- **Gotcha:** "Bare mode does not read `CLAUDE_CODE_OAUTH_TOKEN`." `--bare` is "the recommended mode for scripted and SDK calls, and will become the default for `-p` in a future release" ([headless](https://code.claude.com/docs/en/headless#start-faster-with-bare-mode)). A subscription-token setup therefore relies on non-bare `-p`, and a future default change could break it unless the script pins non-bare behaviour.
- The Agent SDK "runs the Claude Code binary" ([Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)). On a host this means installing Claude Code in the image. The same environment variables apply: "`apiKeyHelper`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` apply to the CLI and the surfaces that wrap it, including … the Agent SDK, and GitHub Actions" ([authentication](https://code.claude.com/docs/en/authentication#credential-management)).
- Operations: the token lasts one year. Usage shares the five-hour and weekly limits with the owner's own claude.ai and Claude Code use: "all activity in both tools counts against the same limits" ([Help Center 11145838](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)). A job that runs near a deadline can fail if the owner has used up their own window.

**Verdict:** feasible on any host that can run the Claude Code binary and hold a secret. It is more fragile than an API key because of shared limits, a yearly token rotation and the bare-mode default change.

### The plain API (fallback)

Analyst mode and Scout mode are single-shot "read input, write text or JSON" calls with no agent loop. They need neither Claude Code nor the Agent SDK: one Messages API call with the official SDK covers each, and the Batch API suits per-Member summaries that no one is waiting on.

## 2. Terms and policy analysis

Which terms apply: Claude Code use on Free/Pro/Max/Ultra plans falls under the **Consumer Terms**. Team, Enterprise and Claude API use falls under the **Commercial Terms** ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#license)).

### Explicitly allowed

| Clause | Source |
|---|---|
| Setup token "for CI pipelines, scripts, or other environments where interactive browser login isn't available" | [authentication](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token) |
| `CLAUDE_CODE_OAUTH_TOKEN`: "Use this for CI pipelines and scripts where browser login isn't available." | [authentication precedence](https://code.claude.com/docs/en/authentication#authentication-precedence) |
| GitHub Actions secret `CLAUDE_CODE_OAUTH_TOKEN`, "an OAuth token that authenticates with your Claude subscription". The docs show a `schedule: cron` workflow, and "If you authenticate with an OAuth token, runs use your Claude subscription instead of API billing." | [GitHub Actions](https://code.claude.com/docs/en/github-actions) |
| Agent SDK and `claude -p` on a plan login still count against subscription limits (June 15, 2026 note: earlier-announced changes to Agent SDK usage "paused") | [Help Center 15036540](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) (paraphrased; verbatim text not captured) |
| Consumer Terms §3 forbids automation "Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it". The documentation above is that explicit permission for scripted use. | [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (effective Oct 8, 2025) |
| Sharing outputs: you may "share Materials with others at your direction" (§4). Outputs are assigned to you. | [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) |
| API path: Anthropic "gives Customer permission to use the Services, including to power products and services Customer makes available to its own customers and end users." | [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) (effective Jun 17, 2025) |

### Explicitly disallowed

| Clause | Source |
|---|---|
| "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications, or to route requests through Free, Pro, Max, or Ultra plan credentials on behalf of their users." | [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use) |
| Developers "may not collect, store, or intermediate Claude.ai credentials or session tokens". This rules out an open-source bot that asks *Members* for their tokens. | same |
| "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." | [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview) |
| "You may not share your Account login information … or make your Account available to anyone else." (§2) | [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) |
| "You agree that you will not use our Services for any commercial or business purposes" (§11, non-commercial use only) | [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) |
| Do not "Resell, proxy, or otherwise provide access to Claude through unauthorized means" | [Usage Policy](https://www.anthropic.com/legal/aup) (effective Nov 12, 2026) |
| Enforcement: "Anthropic reserves the right to take measures to enforce these restrictions and may do so without prior notice." | [legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use) |

### Ambiguous: the FPL Bot's actual shape

The FPL Bot's hosted instance is run by its owner for 5–10 invited Members. It is non-commercial, and Claude writes text from inputs the code prepares.

- **The "on behalf of their users" line.** The Members never sign in to Claude and never send it requests. The owner's job calls Claude and posts the results. One reading: this is the owner's own scripted use with outputs shared "at your direction", which is allowed. The other reading: the bot is a "service" whose users the requests serve, so the developer "should use API key authentication". The docs use "should", not "must", for developers, and reserve "does not permit" for third-party apps offering claude.ai login or routing on behalf of users. No document names a private hobby bot for friends.
- **"Ordinary, individual usage."** "Advertised usage limits for Pro, Max, and Ultra plans assume ordinary, individual usage of Claude Code and the Agent SDK" ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance#acceptable-use)). The volume here is tiny, but "individual" can be read against output produced for ten people.
- **Non-commercial.** The bot is free and private, which satisfies §11 as written. It stops holding if the bot ever charges or carries ads.
- **The open-source angle.** Publishing code that *each deployer* runs with their *own* credentials is fine: the legal page does not "prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription". The bot must never collect a Member's Claude credentials.
- **Usage Policy disclosure.** For "consumer-facing chatbots or AI agents that communicate directly with external users", the policy says operators "must disclose to users that they are interacting with AI". Labelling bot messages as AI-written is cheap and covers this whichever auth path is used. The Usage Policy says nothing on fantasy sports or gambling.

**Bottom line:** subscription-backed automation for the owner's own use is allowed. Subscription-backed output for other people is not explicitly allowed and sits close to two explicit prohibitions. The downside (losing the owner's personal account without notice) is large compared with the API cost (about $1 a season). Only Anthropic can settle the ambiguity: the docs point to [contact sales](https://www.anthropic.com/contact-sales) "for questions about permitted authentication methods for your use case".

## 3. Subscription-native scheduling options

| Option | How it works | Fit for the FPL Bot | Source |
|---|---|---|---|
| **Cloud scheduled tasks** (formerly routines; research preview) | A saved Claude Code config (prompt, repos, connectors, cloud environment) run on Anthropic's cloud on a **schedule**, an **API** trigger (`/fire` with a bearer token, beta header `experimental-cc-routine-2026-04-01`) or **GitHub** events. Available on "Pro, Max, Ultra, Team, and Enterprise plans". Cron can run at most hourly: "Expressions that run more often than once per hour are rejected." Usage: "Scheduled tasks draw down subscription usage the same way interactive sessions do." Limits include 100 scheduled runs an hour per account. The default network policy is an allowlist, so custom domains (the FPL API, news sources, the bot's own endpoint) need the environment's network access changed. Connector actions (Slack and others) "appear as you". | Suits an owner-run **Scout** per Gameweek: clone the repo, read the condensed news, commit adjustments or call the bot's endpoint. It is a "native Anthropic application", so it is the cleanest subscription path for owner work. Delivering to Members still comes from the owner's identity, so the same grey area applies if it posts outputs to them. Research-preview status makes it a poor base for the production path. | [scheduled tasks](https://code.claude.com/docs/en/routines) |
| **GitHub Actions cron + `claude_code_oauth_token`** | The documented `on: schedule: cron` workflow running `anthropics/claude-code-action@v1`. GitHub disables schedules after 60 days without repository activity in public repos. The docs advise an API key for shared/org secrets, since "an OAuth token is tied to the subscription of the person who ran `claude setup-token`". | Works for Scout runs if the bot's data lives in or is reachable from the repo. Same terms reasoning as above. | [GitHub Actions](https://code.claude.com/docs/en/github-actions#run-on-a-schedule) |
| **Self-hosted `claude -p` with `CLAUDE_CODE_OAUTH_TOKEN`** | Any cron on the bot's host. | Technically the simplest. In terms of policy it is the most "product-like" of the three. | [authentication](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token) |
| **Max/Ultra included API credits** (not subscription usage, but included in the plan price) | Link one Console org on claude.ai → Settings → Billing. Credits are $100/month on Max and $200 on Ultra, with no rollover. They cover "Claude API, Claude Managed Agents, the Claude Agent SDK, and playground", and do not cover Claude Code. Pro is not eligible. | **Best of both.** The API key falls under the Commercial Terms with no grey area, and costs nothing beyond a Max plan. | [API credits for subscribers](https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers), [Help Center 17154008](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans) |

Note: the credits cover `claude -p` and the Agent SDK only with an API key from the linked org. Runs started by the Claude Code GitHub Action count as Claude Code usage, and "credits don't cover them, even with `-p`" ([Help Center 17154008](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans)).

## 4. API cost estimate

### Prices used (fetched 2026-11-19 from [pricing](https://platform.claude.com/docs/en/about-claude/pricing))

| Model | Input | 5m cache write | Cache read | Output | Batch in / out |
|---|---|---|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`, prompt ≤100K) | $0.10 | $0.125 | $0.01 | $0.50 | $0.05 / $0.25 |
| Claude Haiku 5.5 (prompt >100K) | $0.50 | $0.625 | $0.05 | $2.50 | $0.25 / $1.25 |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 | $2.50 | $0.10 | $10 | $1 / $5 |
| Claude Opus 5.5 (`claude-opus-5-5`) | $4 | $5 | $0.20 | $20 | $2 / $10 |

All prices are per million tokens. Batch is "a 50 percent discount on both input and output tokens", and caching multipliers "stack with other pricing modifiers, including the Batch API discount". For Haiku 5.5, a request whose prompt exceeds 100K tokens pays the higher tier on the whole request.

### Assumptions

- 38 Gameweeks, 10 Members, a season of about 9.5 months (August to May).
- **Scout run** (Scout mode, 1 per Gameweek): about 45K input tokens (≈3K instructions and schema, ≈30K condensed team news, ≈12K Footballer and fixture context) and about 8K output tokens (structured adjustments plus adaptive thinking). Uncached, because the gap between Gameweeks is a week.
- **Member summary** (Analyst mode explanation, 10 per Gameweek): about 8K input tokens, of which 5K is a shared prefix (2K style and instructions plus 3K Gameweek context) cached across the 10 Members and 3K is Member-specific (Squad, Gaps, recommendations), plus about 2.5K output tokens.
- Season totals: about **4.75M input / 1.25M output tokens**.
- Price alerts are assumed to be pure code with no LLM calls. If Claude writes them nightly, add roughly 10 × 250 nights × 2K in / 300 out ≈ 5M in / 0.75M out. On Haiku 5.5 that is under $1 a season.
- "Heavy" scenario = 3× every token count, covering re-runs after late news, longer news digests, more thinking and Double Gameweeks.
- Batch + cache figures assume cache hits inside a batch. That is best-effort, so treat them as a floor.

### Results

| Model | Scenario | Season, list price | Season, + caching | Season, + caching + Batch | Per month (batch+cache) |
|---|---|---|---|---|---|
| Haiku 5.5 | base | $1.10 | $0.95 | **$0.48** | **≈$0.05** |
| Haiku 5.5 | heavy ×3 (Scout prompt >100K, so the higher tier applies) | ≈$7.20 | ≈$6.70 | ≈$3.40 | ≈$0.35 |
| Sonnet 5.5 | base | $22.04 | $18.89 | $9.44 | ≈$1.00 |
| Sonnet 5.5 | heavy ×3 | $66.12 | $56.66 | $28.33 | ≈$3.00 |
| Opus 5.5 | base | $44.08 | $37.77 | $18.89 | ≈$2.00 |
| Opus 5.5 | heavy ×3 | $132.24 | $113.32 | $56.66 | ≈$6.00 |

To recompute: season cost = 38 × (Scout input × input price + Scout output × output price) + 38 × [shared prefix written once and read 9 times + 10 × (Member-specific input × input price + output × output price)]. Halve the result for Batch.

Takeaways:
- **The cheapest suitable model is Claude Haiku 5.5.** At this volume the model choice is a quality decision, not a cost one: even Opus 5.5 at list price is about $4.60 a month.
- Keep each Scout prompt **under 100K tokens** on Haiku 5.5 (condense news harder, or split the request). Crossing the threshold multiplies that request's cost by 5×.
- The Batch API fits the per-Member summaries (no one waits on them). It does not fit a Scout run made close to a deadline unless it is submitted with plenty of margin, because batches are asynchronous.
- Prompt caching barely matters here, saving about 15%. The shared 5K-token summary prefix is well above the 512-token minimum cacheable prefix for current models (per the claude-api skill; confirm against the prompt-caching docs).
- Claude Haiku 5.5's tokenizer counts about 30% more tokens than Claude Haiku 4.5's (claude-api skill). The token assumptions above already have that much slack.
- A Max plan's $100/month of included credits covers even the Opus heavy scenario about 17 times over.

## 5. Recommendation

1. **Production (the hosted bot serving Members): use an API key, not the subscription.** It falls under the Commercial Terms, which explicitly allow serving end users. It has no shared rate limits with the owner's personal use, no one-year token rotation and no bare-mode surprise. The owner's personal claude.ai account is not exposed to enforcement. Default model: Claude Haiku 5.5 with the Batch API for Member summaries. Move to Claude Sonnet 5.5 only if an eval shows Haiku's Scout adjustments are not good enough. The cost difference is about $10–20 a season.
2. **If the owner has Max (or Ultra):** link a Console org and run the bot on the included monthly credits, at no marginal cost. Give the bot its own workspace with a spend limit.
3. **If the owner has Pro:** Pro gets no included credits, so pay for the API directly. The expected spend is a few dollars a season.
4. **Subscription use that stays clearly in bounds:** the owner's own development, experiments and manual Scout reviews in Claude Code. Optionally, an owner-only cloud scheduled task or GitHub Actions cron that produces artifacts the *owner* reviews.
5. **Never** send Member free text to a subscription-backed Claude, and never ask Members for their Claude credentials.
6. Label bot messages as AI-written. It is cheap and satisfies the Usage Policy's disclosure rule if the bot ever counts as a consumer-facing agent.

## 6. Open questions

- Which plan does the owner have: Pro (no included API credits) or Max/Ultra ($100/$200 a month)? This decides between "free via credits" and "a few dollars a season".
- Will Members ever chat with the bot in free text that reaches Claude? If so, the subscription path is clearly out, and per-request cost estimates for chat are needed.
- Is Claude Haiku 5.5 good enough for Scout adjustments to minutes and Expected points? This needs a small eval against past Gameweeks before choosing between Haiku and Sonnet.
- Does Scout mode need Claude to search the web itself, or does code collect the news? Web search has its own per-search pricing, not costed here.
- Anthropic's position on a private, non-commercial bot whose subscription-generated outputs go to a few invited friends is not documented. Only Anthropic (via [contact sales](https://www.anthropic.com/contact-sales)) can settle it, if the subscription path is still wanted.
- Cloud scheduled tasks are a research preview, and their limits and API may change. Re-check before relying on them.
- The Supplemental Credit Terms ([credit-terms](https://www.anthropic.com/legal/credit-terms), effective Mar 4, 2024) say "Credits may only be used by the holder of the Anthropic account to which the Credits are associated". That is consistent with the owner's bot using them, but the terms predate the subscriber-credit programme.

## Sources

- Claude Code authentication (setup-token, `CLAUDE_CODE_OAUTH_TOKEN`, precedence): https://code.claude.com/docs/en/authentication
- Run Claude Code programmatically (headless `-p`, bare mode): https://code.claude.com/docs/en/headless
- Agent SDK overview (claude.ai-login restriction, Commercial Terms): https://code.claude.com/docs/en/agent-sdk/overview
- Claude Code legal and compliance (authentication and credential use, ordinary individual usage): https://code.claude.com/docs/en/legal-and-compliance
- Claude Code GitHub Actions (OAuth token secret, cron example, costs): https://code.claude.com/docs/en/github-actions
- Cloud scheduled tasks, formerly routines: https://code.claude.com/docs/en/routines
- Consumer Terms of Service (effective Oct 8, 2025): https://www.anthropic.com/legal/consumer-terms
- Commercial Terms of Service (effective Jun 17, 2025): https://www.anthropic.com/legal/commercial-terms
- Usage Policy (effective Nov 12, 2026): https://www.anthropic.com/legal/aup
- Supplemental Credit Terms: https://www.anthropic.com/legal/credit-terms
- Help Center: Use Claude Code with your Pro, Max, or Ultra plan: https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan
- Help Center: Use the Claude Agent SDK with your Claude plan: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- Help Center: Monthly API credits for Max, Ultra, and Team plans: https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans
- Claude Platform: API credits for Max, Ultra, and Team plans: https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers
- Claude Platform: Pricing: https://platform.claude.com/docs/en/about-claude/pricing
- claude-api skill (model ids, tokenizer note, cache minimum; cached 2026-11-03), checked against the live pricing page above
