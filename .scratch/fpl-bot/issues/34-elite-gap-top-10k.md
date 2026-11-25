# 34: Elite gap, top 10k, full sample

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a Member sees where their Squad differs from the top 10k, using our own sample of the official API.
- The post-deadline job (ticket 31) first reads the standings pages that fix the Elite cohort, targeting completion before the first kickoff. Then, after Member and Rival picks, it runs the stratified sampler for the top 10k at ±2% (95%).
- Output per Gameweek and Footballer: ownership, XI share, captain share, EO, chip usage, sample size and margin of error. Only aggregates are stored; sampled managers' IDs and picks are discarded when the job ends. Writes an `elite` completion row.
- `/gap` and `/gap captain` reuse the Gap function and weight from ticket 33 with the Elite XI share and captain share as the reference. Message shape follows `eliteMessage` in [the Gap prototype](../prototypes/19-gap-views-PROTOTYPE.html): header with cohort, Gameweek, sample size and ±margin of error; the edge explanation line; at most 3 per side; "you look like the template" when nothing qualifies.
- Before the first sample exists: "No Elite figures yet for GWn" and a pointer to `/rivals`.

**Blocked by:** 33: Rival gap (`/rivals`)

**Status:** resolved

- [ ] After a post-deadline run on recorded fixtures, `/gap` shows header, both sides (max 3 each) and edges in points per Gameweek.
- [ ] Differences under 2× the margin of error or under 0.35 pts a Gameweek are hidden.
- [ ] `/gap captain` shows the captain part alone.
- [ ] With no Elite figures yet, the bot says so and points to `/rivals`.
- [ ] No sampled manager ID or pick survives the job (asserted on stored rows).
- [ ] The sampler's requests run at the lowest priority of the shared limiter.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 30c5dc0; review fix-ups in 1004dd3). Tests live in `core/tests/`.
