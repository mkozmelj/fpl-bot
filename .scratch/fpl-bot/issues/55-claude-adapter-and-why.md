# 55: Claude adapter, guardrails and `/why`

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the bot's first Claude call, behind guardrails, and the `/why` command that uses it.
- `explain` holds the only Claude client: a protocol with a live adapter (Anthropic SDK, Sonnet 5.5 `claude-sonnet-5-5`, one fixed system prompt, no tools, no prompt caching engineering) and a scriptable fake for tests. Nothing else imports the SDK. `ANTHROPIC_API_KEY` is optional.
- `/why captain|bench|gap` (no argument means captain) recomputes the matching advice and sends Claude only the structured result: Footballer names, numbers and tags. The reply is the templated advice followed by Claude's paragraph.
- Fallback to the plain templated reasons on: no key, API error, call over 20 s, Console spend limit hit, daily cap reached, or a failed numbers guard (names a Footballer or number not in the input, or runs over about 120 words). No retry loop. The Member is never told why.
- Cap: 5 `/why` per Member per UK day, in the existing usage store.
- In-app monthly token ceiling: when reached, Claude is turned off for the month and the owner gets one DM.
- No Member identifiers, team names or chat IDs in any prompt. Prompts and replies are never logged; only counts and token totals.
- `/status` adds whether Claude is configured, `/why` calls today and the month's token total.
- `PRIVACY.md` names Anthropic as a processor for `/why` inputs and `/note` text before this ships.

**Blocked by:** 50: Gap weighted by xP; 52: Mini-league captain state and Rival history; 53: `/bench`: XI, bench order and P(needed)

**Status:** open

- [ ] Normal prose is appended to the template for each of captain, bench and gap.
- [ ] Each fallback trigger (no key, error, timeout, invented number, invented Footballer, too many words, cap reached, ceiling reached) gives the plain template with no mention of why.
- [ ] A captured prompt in a test contains no chat ID, team ID, team name or Member number.
- [ ] The sixth `/why` in a UK day gets the template; the count resets at UK midnight.
- [ ] Reaching the monthly ceiling sends the owner exactly one DM.
- [ ] `PRIVACY.md` is updated in the same PR.
