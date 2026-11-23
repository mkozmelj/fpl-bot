# FPL automation feasibility: can a bot make transfers, and is it allowed?

Research for ticket `issues/11-fpl-automation-feasibility.md`. Researched 2026-11-19 (2026/27 season, before the Gameweek 11 deadline on 2026-11-21 11:00 UTC). No login, account creation or authenticated request was made. Everything below comes from public pages, the public FPL web-app JavaScript, the public OIDC discovery document, unauthenticated API calls, and open-source code and issues read through `gh`.

Each claim carries a tag:
- **[V]**: verified by me against a primary source (official page or bundle, public endpoint, or the client's own source code).
- **[C]**: community report (issue threads, READMEs). Not independently verified.
- **[I]**: my inference.

The terms call a person who plays FPL a "Player". This note says **Manager** for that, following the glossary, and **Footballer** for the real players, which the API calls `element`.

## TL;DR

- **Login works, but it is not a simple API login.** FPL no longer uses the old `users.premierleague.com` form-and-cookie login; that host no longer resolves [V]. Login is now Ping Identity (PingOne) OAuth2/OIDC at `account.premierleague.com`, using the authorization-code flow with PKCE. API calls carry `X-API-Authorization: Bearer <access_token>` [V]. There is no password grant [V].
- **Two ways a bot can get tokens [C]:**
  - Script PingOne's DaVinci login flow with email and password, using a Chrome-impersonating HTTP client. AIrsenal does this.
  - Copy a refresh token from a logged-in browser once, then rotate it with the `refresh_token` grant. Refresh tokens reportedly last about 180 days and rotate on every use.
- **Writes are three POSTs [V]:**
  - `POST /api/transfers/` makes transfers. It also plays the Wildcard or Free Hit, with `chip` set and an empty `transfers` list.
  - `POST /api/my-team/{entry}/` sets the XI, bench order, captain and vice-captain. It also plays Bench Boost or Triple Captain.
  - `POST /api/entry-create/` creates a team.
- **Bot protection [V]:** the login host sits behind Cloudflare Bot Management (it sets a `__cf_bm` cookie). The FPL API host shows no such challenge. No CAPTCHA was reported in the 2025-26 issue threads [C].
- **Fragility [C]:**
  - AIrsenal's scripted login broke three times in 2025/26: August 2025 (migration), October 2025 (DaVinci dropped `interactionToken`) and December 2025.
  - Every client still pointing at `users.premierleague.com` stopped working by July 2026.
  - The `fpl` PyPI package (last release in 2023) cannot log in at all.
- **Terms clause 28(d)** forbids using "automated systems to access the Game and extract information from the Game" [V]. Autopilot is plainly inside that wording [I].
- **Terms clause 6** allows "only one Registration for the Game per user" and says "Individuals are not permitted to register multiple accounts" [V]. The in-game FAQ says "each person may only enter one team" [V]. **A Sandbox account owned by someone who already has a real team breaks the rules whether or not a bot ever touches it** [I].
- **Sanctions (clauses 36-37)** include disqualification and deletion, at the Premier League's "sole discretion", with decisions "final" [V]. A barred Manager "shall not be eligible to participate in the Game under any other identity" [V]. **Being caught on the Sandbox account could therefore cost the owner their real team** [I].
- **Verdict:** Autopilot on a Sandbox account is technically feasible but not permitted. My recommendation [I] is to run Autopilot as a **paper simulation**: no FPL account, decisions replayed against public data. Only touch a real account if the project owner accepts a written ToS risk.

## 1. Auth flow (2025/26 onward, still current in 2026/27)

### What changed
- The legacy login was a POST of `login`, `password`, `app=plfpl-web` and `redirect_uri` to `https://users.premierleague.com/accounts/login/`, followed by cookie auth (`pl_profile`, `sessionid`, `csrftoken`). The unmaintained `fpl` package still does this [V: `amosbastian/fpl` `fpl/fpl.py` `login()`].
- That host is dead.
  - On 2026-11-19, `users.premierleague.com` returned only a dangling CNAME, `plusers.ismfg.net.`, and `curl` failed to resolve it [V].
  - A July 2026 report found NXDOMAIN on 1.1.1.1 [C: rishijatia/fantasy-pl-mcp#21].
- The migration happened at the start of 2025/26 (August 2025), not in 2026/27.
  - AIrsenal users began getting 403s on `my-team/` on 2025-08-14 [C: AIrsenal#729].
  - The fix used a PingOne PKCE flow first shared on the FPLDev Discord [C: AIrsenal#729, and the credit in `fpl_auth.py`].
  - One 2026 README frames this as a "2026/27 OIDC migration". The dates show that is wrong [V/C: issue dates].

### Current flow
**OIDC discovery document** at `https://account.premierleague.com/as/.well-known/openid-configuration` [V]:
- Issuer: `https://account.premierleague.com/as`.
- Endpoints: `/as/authorize`, `/as/token`, `/as/revoke`, `/as/introspect`, `/as/device_authorization`, and the PingOne-specific `ping_end_idp_session_endpoint`.
- `response_modes_supported` includes `pi.flow`, the PingOne marker.
- `grant_types_supported` lists authorization_code, implicit, client_credentials, refresh_token, device_code, CIBA and token-exchange. **There is no `password` grant.**

**The FPL web app is a public OIDC client** [V: `https://fantasy.premierleague.com/assets/index-DZSbhisR.js`, fetched 2026-11-19]:
- Authority: `https://account.premierleague.com/as`.
- `client_id`: `bfcbaf69-aade-4c1b-8f00-c1cb8a193030`.
- `redirect_uri`: the FPL origin.
- Scope: `openid profile email offline_access p1:update:user consent interest`.
- The user (tokens) is stored in `window.localStorage`, and silent renew is used.
- A second client, `c2906aae-cb6e-44d1-838f-0d3565380c06`, is configured with the same authority.

**How the app attaches the token** [V: same bundle]:
- For any request to `/api/`, it reads `access_token` from the stored OIDC user, or falls back to an `ACCESS_TOKEN` cookie scoped to `premierleague.com`.
- It sends that value as `X-API-Authorization: Bearer <token>`, which is not the standard `Authorization` header.

**Scripted login, the AIrsenal approach** [V: `alan-turing-institute/AIrsenal` `src/airsenal/remote/fpl_auth.py`]:
1. GET `/as/authorize` with a PKCE challenge, then scrape an `accessToken` and `state` from the HTML.
2. POST to `/davinci/policy/262ce4b01d19dd9d385d26bddb4297b6/start` to get an `interactionId`.
3. Make three POSTs to `/davinci/connections/{id}/capabilities/customHTMLTemplate`. One of them carries `username` and `password` with `buttonValue: SIGNON`.
4. POST `dvResponse` to `/as/resume`, which redirects with `code=…`.
5. POST `/as/token` with `grant_type=authorization_code` and the code verifier.
6. Verify with `GET /api/me/`.
7. All of this runs through `curl_cffi` with `impersonate="chrome"`, which fakes a Chrome TLS fingerprint.

This is reverse-engineered from PingOne DaVinci's internal UI protocol. It is not a documented API [I].

**Refresh-token approach** [C: kru3ish/fpl-auto-manager README and `fpl_token.py`; rishijatia/fantasy-pl-mcp PR #22, merged 2026-07-31]:
- Copy the `oidc.user:…` entry from the browser's localStorage once.
- After that, `POST /as/token` with `grant_type=refresh_token`, the client ID and the refresh token.
- Reported lifetimes: refresh tokens about 180 days, rotating on every exchange (the old one dies immediately). Access tokens "8 hours" or "several hours" [C]. I did not verify the token lifetimes.
- **Session gotcha** [C: kru3ish README]: tokens carry the Ping session `sid`, and revocation is per session. If the token comes from the browser you normally play in, the next visit to the site can revoke the bot's chain. Use a dedicated browser profile.

### Bot protection
- `account.premierleague.com` is served through Cloudflare and sets `__cf_bm` [V: response headers, 2026-11-19]. Cloudflare documents `__cf_bm` as the cookie behind Bot Management and (Super) Bot Fight Mode, used to compute a bot score [V: Cloudflare cookie docs].
- The API host `fantasy.premierleague.com` is served by Fastly/Varnish. It returned public endpoints to plain `curl` with no challenge [V].
- There are no DataDome, reCAPTCHA, hCaptcha or Turnstile markers in the FPL web-app bundle [V].
  - DataDome did break cookie login in 2023 under the old scheme [C: amosbastian/fpl#127].
  - AIrsenal's use of Chrome TLS impersonation suggests plain Python clients get scored as bots on the login host [I].
- No CAPTCHA appears in the 2025/26 AIrsenal login threads [C: #729, #762, #781].
- The terms ask Managers to enable two-factor authentication "where available" [V: clause 30(d)]. If 2FA is on, a scripted password login would need an extra step, but the refresh-token path would not [I].

## 2. Write endpoints

All paths are under `https://fantasy.premierleague.com/api/` and all need the bearer header. Payload shapes are taken from the official web-app bundle [V: `index-DZSbhisR.js`] unless marked otherwise.

| Action | Request | Body (as the web app sends it) |
|---|---|---|
| Transfers | `POST transfers/` | `{chip, entry, event, transfers:[{element_in, element_out, purchase_price, selling_price}]}`. `chip` is the active transfer-type chip name or `null`. |
| Wildcard or Free Hit | `POST transfers/` | `{chip:"wildcard"\|"freehit", entry, event, transfers:[]}`, then re-GET `my-team/{entry}/` |
| Set XI, bench, captain and vice | `POST my-team/{entry}/` | `{chip, picks:[{element, position, is_captain, is_vice_captain}]}`. Positions 1-11 are the XI and 12-15 the bench order [C: kru3ish README]. |
| Bench Boost or Triple Captain | `POST my-team/{entry}/` | `{chip:"bboost"\|"3xc", picks:[…]}` |
| Read own Squad state | `GET my-team/{entry}/`, `GET me/` | Returns selling prices, bank, free transfers and chip status. These are only available with auth [C/V: AIrsenal `fpl_api.py`]. Unauthenticated `me/` returns `{"player":null}` [V]. |
| Create a team | `POST entry-create/` | Includes `terms_agreed: true` [V: bundle form field; C: kru3ish payload] |

Notes:
- **Chips for 2026/27** [V: public `bootstrap-static/`]: two of each chip, one usable in Gameweeks 1/2-19 and one in 20-38. Wildcard and Free Hit are of type `transfer`; Bench Boost and Triple Captain are of type `team`.
- **Limits** [V: `game_settings`]: `transfers_cap: 20` per Gameweek and `max_extra_free_transfers: 4`. The cap followed the 2022 account-hijacking wave [C: PortSwigger, 2022].
- **Selling price** must come from `my-team/` and can differ from `now_cost`. Prices are in tenths, so 75 means £7.5m [V: bundle `dw` selector; C: kru3ish].
- **Validation errors seen** [C: AIrsenal#840, 2026-08-27]: `transfer_entry_mismatch` ("Entry did not match logged in entry") and `transfer_element_out_not_pick`.
- **Payload difference:** AIrsenal sends `confirmed:false, wildcard:bool, freehit:bool` rather than the web app's `chip` field, and its docstring says Bench Boost and Triple Captain "have to be played on the website" [V: AIrsenal `apply/transfers.py`, `remote/fpl_api.py`]. The web app plays them through `my-team/` [V]. Treat the web app as the source of truth.
- **Lineup quirks** [C: AIrsenal#729]: posting a lineup reportedly errors if nothing changed, and may fail if the team is open in a browser at the same time.

## 3. State of open-source clients (November 2026)

| Client | Auth approach | Status |
|---|---|---|
| `fpl` (amosbastian), PyPI 0.6.35 | Old `users.premierleague.com` form login plus `FPL_COOKIE` | **Broken.** The login host is gone. Last release 2023-08-14, last push 2024-07-26 [V: PyPI, `gh`]. Issue #127 "Login fails" has been open since 2023; a June 2026 comment notes `pl_profile` no longer exists [C]. Read-only public endpoints still work [I]. |
| AIrsenal (Alan Turing Institute) | Scripted PingOne DaVinci PKCE with email and password, via `curl_cffi` Chrome impersonation | **Working and maintained.** v1.16.0 (2026-08-14) and v2.0.0 (2026-09-25), pushed 2026-11-19 [V]. Login broke and was fixed in Aug, Oct and Dec 2025 [C: #729, #762/#763, #781]. An August 2026 issue shows login succeeding and the transfer validator replying [C: #840]. Can make transfers and set lineups. |
| fantasy-pl-mcp (rishijatia), PyPI 0.3.2 | Refresh token pasted from the browser, rotated with `refresh_token` | **Working.** Migrated in PR #22 (2026-07-31), released 2026-11-06 [V]. |
| kru3ish/fpl-auto-manager | Refresh token, with optional Playwright re-mint in an isolated browser profile | New (2026-08), 0 stars, self-described autopilot. Its README documents the endpoints and the session-revocation trap [C]. |
| Others found | Bearer-header or `/as/token` code in about 30 small repos (e.g. `laduygaga/fpl-picker`, `gmanreviews/fpl-dotnet-client`, `mgphp/fpl-mcp`, `nplol/fantasypl` with Playwright headless login) | Varying quality; not assessed individually [V: `gh search code`]. |

Takeaways [I]:
- No client uses an official API, because none exists.
  - AIrsenal's maintainer: "FPL have never officially supported/exposed the API and they frequently make breaking changes to how the authentication works" [C: AIrsenal#762].
  - Expect at least one auth break per season, each costing a day to a week of engineering.

## 4. Terms and account risk

Source: FPL Terms & Conditions, `https://fantasy.premierleague.com/help/terms`. The text comes from the `Terms-DUOzP1QV.js` chunk served 2026-11-19 [V]. The Premier League's 2026-27 broadcaster-league terms link to this page as the "general Fantasy Premier League Terms and Conditions" [V]. Its prize dates still refer to May and June 2026, so the served text may not yet have been refreshed for 2026/27 [I].

### Relevant clauses [V], quoted
- **5:** "Registrations must not be made by agents or third parties."
- **6:** "only one Registration for the Game per user of the Site or App is permitted. Individuals are not permitted to register multiple accounts on the Site or App. Individuals are not permitted to provide any other person with access to their account…"
- **27:** Managers must keep passwords secure and "shall not allow any other person access to your account nor share or transfer registration or control of your account with or to another person."
- **28(d):** Managers shall not "use automated systems to access the Game and extract information from the Game". Clause 28 also bars "spamming or flooding" (c) and unauthorised access (e).
- **30(d):** Managers are responsible for credential security "including enabling two-factor authentication where available".
- **36:** On any breach, the Premier League may, "in its sole discretion", refuse entry, disqualify, "modify, delete and/or suspend your Registration", and "delete all related information". "All such decisions … will be final."
- **37:** "If you are barred or disqualified … you shall not be eligible to participate in the Game under any other identity or team name."
- **In-game FAQ** (`/help/faqs`, same bundle): "In the interest of fair play each person may only enter one team."

### Site-wide PL terms of use
`premierleague.com/en/terms-and-conditions` bars unauthorised access, creating databases from downloaded material, and commercial use. On breach, "your right to use the Website and App will cease immediately" [V]. One Premier League account (the `account.premierleague.com` identity, with an `ACCESS_TOKEN` cookie scoped to `premierleague.com` [V: bundle]) serves FPL and the other PL properties. A sanction could therefore reach beyond FPL, though no source confirms that [I].

### Risk analysis [I]
- **Autopilot on any account breaches 28(d).** Logging in with a bot and reading `my-team/` is "automated systems … access … and extract information". The clause is conjunctive ("access … and extract"), but Autopilot does both.
- **Advice mode is not entirely clean either.** The bot polls public endpoints automatically, which arguably also fits 28(d). The difference is that no account is involved, so there is nothing to suspend. The worst case is IP rate-limiting. A large tolerated ecosystem (AIrsenal, MCP servers, analytics sites) reads these endpoints [I].
- **A Sandbox account is itself the main rules problem.** If the project owner already plays FPL, a second Premier League account is "multiple accounts" (clause 6) and a second team (FAQ). That holds even with no automation at all.
- **An entry can't share the owner's real login.** The web app models one `entry` per logged-in account (`me/` returns a single `player`, and transfers are checked against the "logged in entry") [V/C]. So a Sandbox account must be a separate Premier League account with a separate email.
- **Risk to the owner's real team.** If FPL links the Sandbox account to the owner (shared name, IP, device, or payment and contact data — I don't know what FPL can see), clause 37 lets it bar the person "under any other identity". That would put the real team, and with it the real mini-league standings, at risk. I found no public record of FPL detecting multi-accounting or bot use.
  - It does remove teams at its discretion: the 2019/20 overall leader's team was "removed … due to a breach of our terms" [C: Kotaku, 2020]. That case was about conduct, not automation.
  - kru3ish's README says "managers have been banned for automating team management" but cites nothing [C, unverified].
- **Credential and token risk.** A refresh token is a roughly 180-day credential that can modify the team [C]. Clause 27 forbids letting another person control the account. Running Autopilot as a hosted service for other people's accounts would breach clause 27 and concentrate credential risk [I]. That is why kru3ish refuses to host [C].
- **Operational risk.** Writes are irreversible (transfers, hits, chips). Auth breaks silently, for example the six-day dead chain kru3ish reported [C].

## 5. Feasibility verdict: Autopilot on a Sandbox account

| Dimension | Verdict |
|---|---|
| Technically possible | **Yes.** Every action Autopilot needs (transfers, XI and bench, captain and vice, all four chips) is a JSON POST with a bearer token [V]. |
| Reliability | **Medium-low.** It depends on a reverse-engineered login: AIrsenal-style DaVinci scripting behind Cloudflare bot scoring, or browser-sourced rotating refresh tokens. Expect breaks every few months, judging by three in 2025/26 [C]. |
| Allowed by the terms | **No.** Clause 28(d) covers the automation. Clause 6 and the FAQ cover the Sandbox account whenever its owner also has a real team [V clauses; I application]. |
| Risk to the Sandbox account | Deletion or disqualification at sole discretion, with no appeal (clause 36) [V]. Enforcement likelihood is unknown and probably low for a quiet single account [I]. |
| Risk to the owner's real team | **Real but unquantified.** Clause 37 lets a sanction follow the person [V/I]. This is the decision-relevant risk. |

**Recommendation [I], in order of preference:**
1. **Paper Autopilot (no account).** Run the same decision engine against public `bootstrap-static/`, `fixtures/`, `event/{gw}/live/` and `entry/{id}/…` data. Keep a simulated Squad, bank, free transfers and chips in our own state, and score it each Gameweek with FPL's scoring rules.
   - This tests everything Autopilot is meant to test, except the write calls, with zero ToS or account exposure.
   - It matches the Advice-mode architecture, where Members make every change themselves.
2. **If live writes are required:** use a Sandbox account only if it belongs to a person with **no other FPL team**, who consents and holds the risk in writing. That is effectively their only and real team, which conflicts with the glossary's Sandbox definition.
   - Use the refresh-token path from a dedicated browser profile, not password scripting.
   - Hard rails: a kill switch, no hits, a write log, and one transfer per Gameweek.
   - Accept that clause 28(d) is still breached.
3. **Don't** create a second account for someone who already plays FPL. **Don't** hold Members' tokens. **Don't** host Autopilot as a service.
4. Optionally, ask the Premier League (`info@premierleague.com`, listed in the terms) for written permission. Clause 28(b) contemplates use "expressly permitted". The answer is likely no, but a yes would remove the risk [I].

## 6. Open questions

- **Detection.** Does FPL detect or act on automated writes or multi-accounting (IP, device, email similarity)? I found no public evidence either way.
- **Token lifetimes.** Exact access-token TTL: "8 hours" and "several hours" are both reported and neither is verified. Refresh-token TTL ("about 180 days") is also unverified. Verifying either needs an authenticated session, which was out of scope.
- **Bot scoring.** Does Cloudflare Bot Management on `account.premierleague.com` challenge scripted DaVinci logins from datacenter IPs, for example a cloud cron, as opposed to home IPs? The issue threads come from home machines.
- **2FA.** Does the PL account now offer or enforce 2FA, and does that break scripted password login?
- **Terms version.** Will the 2026/27 terms change clause 28(d) or 6 when the page is refreshed? The served copy still carries 2025/26 prize dates.
- **Project decision.** Is the Sandbox owner someone who already plays FPL? If yes, option 2 is off the table and only paper Autopilot remains.

## Sources

Official / primary:
- FPL Terms & Conditions: https://fantasy.premierleague.com/help/terms (content chunk https://fantasy.premierleague.com/assets/Terms-DUOzP1QV.js, fetched 2026-11-19)
- FPL FAQ (one team per person): https://fantasy.premierleague.com/help/faqs (text in https://fantasy.premierleague.com/assets/index-DZSbhisR.js)
- FPL web-app bundle (OIDC config, `X-API-Authorization`, `transfers/` and `my-team/` payloads): https://fantasy.premierleague.com/assets/index-DZSbhisR.js
- PL account OIDC discovery: https://account.premierleague.com/as/.well-known/openid-configuration
- Public FPL API (chips, `game_settings`): https://fantasy.premierleague.com/api/bootstrap-static/ ; unauthenticated `https://fantasy.premierleague.com/api/me/`
- PL 2026-27 broadcaster-league terms (links the general FPL terms): https://www.premierleague.com/en/terms-and-conditions/2026-27/sky-sports-broadcaster-league
- PL site terms of use: https://www.premierleague.com/en/terms-and-conditions
- Cloudflare cookie reference (`__cf_bm`): https://developers.cloudflare.com/fundamentals/reference/policies-compliances/cloudflare-cookies/

Open-source code:
- amosbastian/fpl `login()`: https://github.com/amosbastian/fpl/blob/master/fpl/fpl.py ; PyPI: https://pypi.org/project/fpl/
- AIrsenal auth: https://github.com/alan-turing-institute/AIrsenal/blob/main/src/airsenal/remote/fpl_auth.py ; API client: https://github.com/alan-turing-institute/AIrsenal/blob/main/src/airsenal/remote/fpl_api.py ; transfer payload: https://github.com/alan-turing-institute/AIrsenal/blob/main/src/airsenal/apply/transfers.py
- fantasy-pl-mcp auth manager: https://github.com/rishijatia/fantasy-pl-mcp/blob/main/src/fpl_mcp/fpl/auth_manager.py ; PyPI: https://pypi.org/project/fantasy-premier-league-mcp/
- kru3ish/fpl-auto-manager README and `fpl_token.py`: https://github.com/kru3ish/fpl-auto-manager

Issues and community reports:
- amosbastian/fpl#127 "Login fails" (DataDome, `pl_profile` gone): https://github.com/amosbastian/fpl/issues/127
- AIrsenal#729 (August 2025 auth migration): https://github.com/alan-turing-institute/AIrsenal/issues/729
- AIrsenal#762 and PR #763 (October 2025 `interactionToken` removal): https://github.com/alan-turing-institute/AIrsenal/issues/762 , https://github.com/alan-turing-institute/AIrsenal/pull/763
- AIrsenal#781 (December 2025 break): https://github.com/alan-turing-institute/AIrsenal/issues/781
- AIrsenal#840 (2026/27 transfer validation errors): https://github.com/alan-turing-institute/AIrsenal/issues/840
- fantasy-pl-mcp#21 (`users.premierleague.com` NXDOMAIN) and PR #22: https://github.com/rishijatia/fantasy-pl-mcp/issues/21 , https://github.com/rishijatia/fantasy-pl-mcp/pull/22
- PortSwigger, FPL account hacks, 20-transfer cap and 2FA (2022): https://portswigger.net/daily-swig/fantasy-premier-league-account-hack-surge-prompts-plans-to-introduce-extra-login-checks-for-football-fans
- Kotaku, 2019/20 leader removed for breach of terms: https://kotaku.com/fantasy-football-champion-disqualified-over-allegedly-r-1844692571
