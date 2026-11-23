# 36: Nightly Price alert

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** each Member gets at most one plain-text message a night warning of likely price changes that matter to them, built on FPL's own projection fields in `bootstrap-static` (ticket 15 is the source of every rule here).
- Timing: at the Member's alert time in their timezone (default 20:00), clamped to 17:00-23:15 UK. Members sharing a send time share one fetch. No second correction ping.
- Content: owned Footballers (last-deadline Squad) only for falls, Watch-list Footballers only for rises, likelihood ±4 (Likely) and ±5 (Very likely) only.
- Format:
  - Header "Price alert · GWn · tonight 00:00 UK".
  - "Likely to fall (you own)" and "Likely to rise (Watch list)", each only if non-empty. Each line: name, position, club, price → new price, Very likely / Likely, and any injury or doubt status on owned Footballers.
  - Very likely before Likely, then by name.
  - An optional one-line "Tomorrow night" for ±5 only; a Footballer listed tonight is not repeated; day 3 is never shown.
  - One savings line stating the £0.1m, with no transfer recommendation.
  - On the night before a deadline, or whenever the Squad could be stale: "Based on your Squad at the last deadline. Ignore any you've already sold."
- Silence: nothing to report, or projection fields missing, `price_change_calibrating`, or `bootstrap-static` unreachable. A failed fetch is retried once after 10 minutes, within the 23:15 UK cut-off; if the data still fails, the owner gets one DM that night and Members get nothing.
- No Wildcard or Free Hit logic. No Claude call.

**Blocked by:** 27: Polite FPL client and owner incident DMs; 29: Watch list; 30: `/squad` and join backfill

**Status:** ready-for-agent

- [ ] With a fake clock, a Member at 20:00 Europe/Ljubljana gets the alert at the corresponding UK time; a time outside 17:00-23:15 UK is clamped.
- [ ] Content, ordering, status flags, tomorrow line, no-repeat rule and savings line match the format above on recorded fixtures.
- [ ] Owned rises and Watch-list falls are never mentioned.
- [ ] The stale-Squad caveat appears the night before a deadline.
- [ ] A quiet night sends nothing.
- [ ] Missing fields or `price_change_calibrating` send nothing to Members.
- [ ] An unreachable `bootstrap-static` is retried once after 10 minutes, then the owner gets exactly one DM and Members nothing.
- [ ] Two Members with the same send time cause one fetch.
