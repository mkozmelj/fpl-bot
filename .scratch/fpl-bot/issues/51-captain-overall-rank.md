# 51: `/captain` for the Overall rank Goal

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** on-demand captain and vice-captain advice, as pure functions in `advice` and a fixed template in delivery. No Claude call and no push.
- Shared advice basis (used by later tickets too): the last-deadline Squad, or the Squad from the Gameweek before if the last deadline used a Free Hit; the current xP table from the model in use; a header with the Gameweek, "based on your GWn Squad" and the model in use; the hidden-picks caveat between deadlines.
- Captain: highest next-Gameweek xP (doubles summed, blanks 0); top 3 shown with xP. Options within 0.3 xP are tied and read "too close to call", naming the tie-break.
- Tie-break: the higher Elite captain share, from the top 10k cohort for Members ranked in the top 100k, otherwise the top 100k. If that figure is missing or stale, the higher xP wins and the message says so. No EO risk term.
- Vice-captain: the best-xP starter from a different match with start probability ≥ 0.85; if the captain has a double Gameweek, the next best Footballer who passes the rule.
- Reasons are tagged Evidence (xP) or Practice (Elite share). The functions take a chip-active flag; Phase 2 always passes "none".
- A Member whose Goal is Mini-league gets the same Overall rank advice until ticket 52 lands.

**Blocked by:** 49: xP job, storage and `/status`

**Status:** open

- [ ] A clear captain shows the top 3 with xP and an Evidence tag.
- [ ] A tie is broken by Elite captain share and says so; with stale or missing Elite figures, xP wins and the message says so.
- [ ] Vice-captain comes from a different match and meets the 0.85 floor; the double-Gameweek case is covered.
- [ ] A Free Hit at the last deadline makes the advice use the reverted Squad.
- [ ] The hidden-picks caveat and the model-in-use label appear.
- [ ] Nothing is sent unless the Member asks.
