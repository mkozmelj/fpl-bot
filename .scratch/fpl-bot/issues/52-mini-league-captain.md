# 52: Mini-league captain state and Rival history

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** when a Member's Goal is Mini-league, `/captain` adjusts to their standing against their Rivals. XI, vice-captain and bench stay xP-driven.
- Rival history: after `gw_final`, for Members whose Goal is Mini-league, fetch `entry/{id}/history` for the nearest Rival above and below in the Goal league and store their per-Gameweek points. Kept for the season and deleted with the league, like Rival picks.
- State: z = L / (σ√n) against each of those Rivals, with n the Gameweeks left. σ is the empirical standard deviation of the weekly points difference, shrunk toward 15 when fewer than 8 Gameweeks exist. Ahead z ≥ +1, Behind z ≤ −1, Close otherwise; Hopeless is z ≤ −2 with n ≤ 4.
- Ahead: within the tie band, match the Rivals' most common captain. Close: Overall rank rules with Rival captain share in place of Elite. Behind (n ≤ 6): if a captain the leading Rival lacks is within 10% of the top xP, recommend it, labelled a variance choice and never "better"; otherwise keep the top-xP pick. Hopeless: say so honestly and suggest switching the Goal to Overall rank.
- The reason line carries the Goal risk tag.

**Blocked by:** 51: `/captain` for the Overall rank Goal

**Status:** open

- [ ] Each state (Ahead, Close, Behind with a differential, Behind without one, Hopeless) has a scenario test through the delivery seam.
- [ ] σ uses the prior with fewer than 8 Gameweeks of history.
- [ ] Rival history is fetched only for Members with the Mini-league Goal, and deleted when no Member follows the league.
- [ ] A differential is labelled a variance choice.
- [ ] XI, vice-captain and bench are unaffected by the Goal.
