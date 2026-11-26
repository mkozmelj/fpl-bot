# 53: `/bench`: XI, bench order and P(needed)

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** on-demand XI and bench advice on the shared advice basis from ticket 51.
- XI: the maximum xP over legal formations (1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD), by enumeration in plain code. No solver.
- Bench: the backup goalkeeper is always the sub goalkeeper. Outfield subs are ordered by P(needed) × xP-if-plays. P(needed) comes from start probabilities and formation legality in plain code, with no simulation, and is shown per sub.
- Warning: a starter with start probability below 0.5 that no legal autosub can cover.
- Template: the shared header, the XI by position, the bench order with P(needed), any warning, Evidence tags. Takes the chip-active flag (Bench Boost orders the bench as starters); Phase 2 passes "none".

**Blocked by:** 51: `/captain` for the Overall rank Goal

**Status:** open

- [ ] The XI is legal and has the highest total xP among legal XIs (checked against brute force in a test).
- [ ] A doubtful starter raises the P(needed) of the sub who would replace him.
- [ ] The uncoverable-blank warning appears when, and only when, the rule says.
- [ ] Free Hit reversion and the hidden-picks caveat behave as in `/captain`.
