# 29: Watch list

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a Member manages the Footballers they're thinking of buying, so the Price alert (ticket 36) can warn about rises. Footballer names come from the in-memory `bootstrap-static`. Behaviour follows the `/watch` branch and `watch_pick` step of [the prototype](../prototypes/14-telegram-flow-PROTOTYPE.html).

**Blocked by:** 28: Join flow, settings and `/leave`

**Status:** ready-for-agent

- [ ] `/watch` lists each Footballer with club, position and price, or says the list is empty with an example.
- [ ] `/watch add <name>` adds a single match and confirms with club, position and price.
- [ ] An ambiguous name shows one button per match; tapping one adds it; a stale button is ignored as elsewhere.
- [ ] Adding a Footballer already on the list, an unknown name, or a 21st Footballer each get the prototype's reply and change nothing.
- [ ] `/watch remove <name>` removes a match from the list, or says it isn't there.
- [ ] Watch list rows go when the Member leaves.
- [ ] Tests through the seam cover the prototype's "Ambiguous Watch list" walkthrough.
