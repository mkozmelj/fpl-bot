# Can a bot make transfers on an FPL account, and is it allowed?

Type: research
Status: resolved
Blocked by: —

## Question

For the Autopilot experiment on a Sandbox account:
- How does FPL login work now? Cover the auth flow, cookies or tokens, and bot protection such as captchas.
- Which endpoints make transfers, set the captain and bench, and play Chips?
- How do existing open-source clients (for example the `fpl` Python package) handle this, and do they still work in 2026/27?
- What do the FPL terms say about automated play? What is the risk to a Sandbox account, and to the owner's real account if it is linked to the same Premier League login?

Findings go in `.scratch/fpl-bot/research/11-fpl-automation-feasibility.md`.

## Answer

- **Auth:** the old `users.premierleague.com` cookie login is gone; that host no longer resolves. FPL now uses PingOne OAuth2/OIDC (PKCE) at `account.premierleague.com`, and API calls carry `X-API-Authorization: Bearer <token>`. There is no password grant. Bots get tokens in one of two ways:
  - scripting PingOne's DaVinci login flow behind Cloudflare bot scoring (AIrsenal does this);
  - copying a rotating refresh token, reportedly valid about 180 days, from a dedicated browser profile.
- **Writes:**
  - `POST /api/transfers/` makes transfers and plays the Wildcard or Free Hit.
  - `POST /api/my-team/{entry}/` sets the XI, bench, captain and vice-captain, and plays Bench Boost or Triple Captain.
  - Both are verified against the official web-app bundle.
- **Clients:**
  - The `fpl` PyPI package is broken (last release 2023).
  - AIrsenal and fantasy-pl-mcp work in 2026/27, but AIrsenal's login broke three times in 2025/26, so expect breaks every season.
- **Terms:**
  - Clause 28(d) bans "automated systems to access the Game and extract information".
  - Clause 6 and the FAQ allow one account and one team per person. A Sandbox account owned by someone who already plays breaks the rules even without a bot.
  - Clauses 36-37 allow disqualification or deletion at sole discretion, and bar the person "under any other identity". That puts the owner's real team at risk.
- **Verdict:** technically feasible, not permitted. I recommend paper Autopilot: simulate the Squad against public data with no account. Live writes should run only on the single account of a consenting person who has no other team, with the risk accepted in writing.
- Full findings: [../research/11-fpl-automation-feasibility.md](../research/11-fpl-automation-feasibility.md)

## Comments

- 2026-11-19, owner decision: Autopilot runs as a **paper simulation** only, with no FPL account, no login and no writes. Live writes on any account (Sandbox, second account or a friend's) are ruled out of scope. Follow-up: [Autopilot paper simulation: rules and how it's shown](17-autopilot-paper-simulation.md).
