# Autopilot paper simulation: rules and how it's shown

Type: grilling
Status: resolved
Assignee: claude-session
Blocked by: 13

## Question

How does the Autopilot paper simulation work and how do Members see it? Decide:

- **Start and reset:** the start Gameweek (GW20, with the second chip set?) and the starting Squad (built by the solver on a £100m budget, or a copy of a Member's Squad).
- **Locking:** decisions lock before each deadline, so they can never be changed after it.
- **Scoring:** fidelity against public data — `event/{gw}/live`, auto-subs, vice-captain, chip effects, selling prices and free transfers.
- **How it's shown:**
  - as a Rival in mini-league views
  - an estimated overall rank, from points against the public overall standings
  - a weekly comparison with each Member
- **Variants:** one simulation, or several (an Overall-rank Goal engine against a Mini-league Goal engine) to compare strategies.
- **Accuracy:** how its results also serve as the end-to-end check of advice quality, alongside the xP self-evaluation.

## Answer

Resolved by grilling with the owner, 2026-11-19. The owner widened the first proposal (one Ghost Squad plus an owner-only baseline) into several Ghost Squads, one per tactic.

**Start**
- Autopilot starts at the first Gameweek at or after GW20 in which the solver and xP are ready, so it always has the full second chip set. The first-half Chips are never simulated.
- Every Ghost Squad begins with a free solver build on a £100m budget and 1 free transfer. No Member's Squad is copied.

**Locking and visibility**
- Decisions (transfers, XI, captain, vice-captain, bench, Chip) are computed right after the deadline −90 min fetch, then written as a locked, timestamped record that is never recomputed or edited.
- If a run fails, the Ghost Squad rolls its Squad over with no transfers and the owner is told.
- Members see picks only after the deadline has passed.

**Scoring**
- Full FPL rules from public data: `event/{gw}/live` (final bonus once the Gameweek is final), auto-subs by formation, vice-captain, Chip effects, −4 per extra transfer, free-transfer banking, and selling prices at half the rise (rounded down) from our own price snapshots.
- Acceptance test: the scorer replays a real Member's season from public history and must match FPL's official points exactly. A mismatch blocks Autopilot from going live.
- Anything the data can't settle is a documented assumption.

**Tactics** (all share data, rules, locking and scorer; only settings differ)
- **Core:** maximise xP over 6–8 Gameweeks, no hits, EO risk 0.
- **Template:** EO-weighted toward the Elite cohort (+0.15), template captain.
- **Differential:** EO-weighted away (−0.15), with 1–3 deliberate sub-10% picks.
- **Active:** takes hits when the decayed xP gain clearly beats 4 plus the free transfer given up.
- **Patient:** rolls free transfers, moving only on injuries or big fixture swings.
- **Baseline:** the Core engine fed FPL's own `ep_next`, to test whether our xP adds value.
- Chip timing follows each tactic's own objective. A price-chasing and a Mini-league-Goal Ghost are left out for now and can be added later as new settings.
- Settings are frozen at a Ghost's start and never tuned mid-run. A new tactic is a new Ghost, labelled with its own start Gameweek.

**How Members see it**
- Only **Core** appears in Followed league tables, as a labelled "simulated" Rival row ranked by its own points.
- `/ghost` is on demand: a leaderboard of all six, with each Ghost's Squad and Chip use after the deadline and the Member's own points beside them.
- A rough overall position as a band (top 10k, top 100k, or below), from the cut-off points our own Elite sampler already collects. It is labelled "estimated from our own sample" and is never an exact rank.
- No unsolicited messages.

**Judging**
- Ghosts are compared on realised points and on xP, since decisions are judged on xP, not luck.
- No "winner" is named before GW38. Until then results are labelled "indicative, small sample".
- The Baseline-versus-Core gap is the end-to-end check on our xP, next to the xP self-evaluation.

**Budget:** at most 6 Ghost Squads, solved one after another after the −90 min fetch. If [Probe Railway: FPL reachability and solver timing](18-probe-railway.md) shows they don't fit, the roster shrinks: Active drops first, then Patient, Differential and Template. Baseline and Core stay. The roster is confirmed once the probe reports solve times.

**Glossary:** Autopilot now runs several Ghost Squads, and **Tactic** is added. No ADR: each choice is cheap to change.
