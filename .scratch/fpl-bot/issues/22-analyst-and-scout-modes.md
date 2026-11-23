# Analyst-mode summaries and the fate of Scout mode

Type: grilling
Status: resolved
Assignee: owner
Blocked by: —

## Question

Sonnet 5.5 via the API is decided. What does Claude write per Member in Analyst mode, with what token budget, prompt caching and templated fallback? Does Scout survive as a separate mode, or fold into Analyst mode with Claude kept only for Member-pasted notes (see [Legal free team-news sources for Scout mode](10-news-sources-for-scout.md))? How do we check Scout improves xP?

## Answer

Resolved by grilling with the owner, 2026-11-22.

- **Where Claude writes:** only in an on-demand `/why` command. The Member asks why a recommendation was made (captain, transfer, Gap) and Claude adds "because…" prose around the templated advice. There is no scheduled per-Member brief and no push. Price alerts, captain and bench stay templated with no Claude call. Phase 3 transfer and chip explanations reuse `/why`. Cap: 5 `/why` calls per Member per day. This replaces the earlier plan for a Batch API for Member summaries.
- **Scout is not a mode:** it becomes a shared once-per-Gameweek pipeline step. Plain regex parses the FPL `news` fields, and Claude sees only unparsed leftovers, so the job costs nothing when there are none. "Scout mode" becomes "Scout overrides" in the glossary, defined as the minutes adjustments from team news. Analyst mode is the only mode a Member sees.
- **Member notes:** `/note <text>`, at most 500 characters and 3 per Member per Gameweek. A note affects only that Member's own advice (a per-Member overlay on the pure xP function) and expires at the next deadline. It never enters the shared job. Claude's output is parsed against the strict schema from [Security](16-security-and-open-source-hygiene.md): Footballer ID, minutes change, confidence.
- **Guardrails:**
  - **Fallback:** the plain templated text is used if there is no API key, the spend limit is hit, the API errors or a call takes over 20 s. There is no retry loop, and the Member is never told about spend.
  - **Numbers guard:** `/why` prose is rejected, and the fallback used, if it names a Footballer or number not in the structured input, or runs over about 120 words.
  - **Calls:** no tools, no network, and no identifiers in the prompt.
  - **Budget:** a hard monthly Console limit plus the in-app daily cap.
  - **Caching and batching:** one fixed system prompt with no caching engineering (prompts are too small to matter), and the Scout leftover call is synchronous.
- **Checking Scout helps:** news history can't be backtested, so it runs forward in shadow. Each Gameweek the bot stores xMins and xP with and without overrides (aggregates of its own predictions, not Member tracking), scores both against actual minutes and points, and shows the comparison through owner-only `/accuracy`. Regex-derived overrides are live from day one. Claude-derived overrides (leftovers and notes) stay logged but off until they beat the no-override baseline on minutes MAE over at least 8 Gameweeks with a minimum sample of affected Footballers. If they never do, the Claude parsing path is deleted, and `/why` is unaffected.
