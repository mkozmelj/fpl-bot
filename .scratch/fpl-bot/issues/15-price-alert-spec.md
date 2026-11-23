# What the nightly Price alert says and when it fires

Type: grilling
Status: resolved
Assignee: claude-session
Blocked by: 04, 13

## Question

Given how price changes work and the data we'll have, what goes into the Price alert?
- the probability or confidence threshold for "may fall" and "may rise"
- whether to include a "tonight versus within 2–3 days" horizon
- the suggested action ("sell before the drop?"), and when it's worth it
- the message format
- silent nights
- behaviour around deadlines and Wildcard weeks
- how we measure the predictor's own accuracy (predicted versus actual changes; no Member tracking)

## Answer

Resolved by grilling with the owner, 2026-11-19. Built on the official `price_change_projections` ([How FPL price changes work and how to predict them](04-price-change-mechanics.md)) and the snapshots in [Which data the bot collects, how often, and what it keeps](13-data-ingestion-design.md).

**Content**
- **Threshold:** likelihood ±4 (Likely) and above. Owned Footballers appear only for falls and Watch-list Footballers only for rises. Other directions are never mentioned.
- **Horizon:** tonight is the main section. A one-line "tomorrow night" appears only for ±5 (Very likely). Day 3 is never shown, and a Footballer already listed tonight isn't repeated.
- **Action:** state the fact and the saving only, with no transfer recommendation (that is Phase 3). Example: "If you were planning to sell him anyway, doing it before 00:00 UK saves £0.1m." An owned Footballer who is also flagged doubtful or injured gets that status shown. For the Watch list: "buy now to avoid paying £0.1m more".

**Format:** one plain-text Telegram message, no Claude call.
- Header: "Price alert · GW · tonight 00:00 UK".
- Section "Likely to fall (you own)" and section "Likely to rise (Watch list)". Each section appears only if it isn't empty. Each line has name, position, club, price → new price, a Very likely / Likely label, and any status flag.
- Order: Very likely before Likely, then by name.
- An optional "Tomorrow night" line, then one savings line at the bottom.
- On the night before a deadline, or whenever the Squad could be stale, one caveat line: "Based on your Squad at the last deadline. Ignore any you've already sold."

**Timing**
- One alert a night, at the Member's chosen time (default 20:00 local), clamped to 17:00–23:15 UK. `/time` tells the Member when it clamps.
- No second "late correction" ping in v1. The 23:00 and 23:45 snapshots serve accuracy measurement only.
- No Wildcard or Free Hit logic, since the bot can't see a chip before the deadline passes.

**Silent nights and failures**
- Nothing to report, or data missing (fields absent, `price_change_calibrating`, `bootstrap-static` unreachable): Members get nothing.
- On a data failure the owner gets one direct message that night. A fetch failure is retried once after 10 minutes, within the 23:15 UK cut-off.

**Accuracy of the predictor itself** (no Member tracking)
- For every Footballer, store the projection code at the alert time next to the actual change from the 00:10 `/stats/price-changes/` archive.
- Hit rate per code (−5..+5), for tonight and for tomorrow, plus a season total.
- Read through an owner-only `/accuracy` command. Nothing goes to Members.
- **Floor:** 70% for ±4 and 85% for ±5, over a rolling 14 nights with at least 20 predictions per bucket. Below it, `/accuracy` shows a flag and the owner raises the threshold by hand. Nothing changes automatically.
- The shadow predictor stays unbuilt unless FPL's fields disappear or stay miscalibrated.

**Glossary and ADR:** the existing **Price alert** definition still holds. No ADR: every choice here is cheap to change.
