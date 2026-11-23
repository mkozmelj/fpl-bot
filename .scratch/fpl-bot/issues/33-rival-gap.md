# 33: Rival gap (`/rivals`)

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a Member sees where their Squad differs from their nearest Rivals, on demand only.
- The post-deadline job (ticket 31) also fetches picks for the Rivals in each Followed league and the H2H opponent. Rival picks are kept for the season and deleted when no Member follows that league.
- The Gameweek-final job (ticket 32) first fetches `event/{gw}/live` once and stores per-Gameweek Footballer stats (kept across seasons). A launch backfill fetches it for every finished Gameweek.
- The Gap is a pure function in `advice` taking plain data. The weight is a swappable input so Phase 2 can pass xP instead:

  ```
  edge(f) = (you start − ref XI share) × w(f) + (you captain − ref captain share) × w(f)
  w(f)    = average points over the last 4 finished Gameweeks   (Phase 1)
  shown   = at most 3 per side, only if |difference| > 2 × margin of error and |edge| ≥ 0.35
  ```
  (From `computeGap` in [the Gap prototype](../prototypes/19-gap-views-PROTOTYPE.html); for Rivals the margin of error is 0. The prototype's `net` total is **not** shown.)
- `/rivals`: the nearest 2 above and 2 below by rank in the Goal league (Followed league when the Goal is Overall rank). `/rivals all`: everyone in that league. A head-to-head opponent is a single Rival. Message shape follows `rivalMessage` in the prototype: "You back, they mostly don't" / "They back, you don't", then "Captain: X · N of M Rivals captain him too."
- Between deadlines the message uses the last-deadline Squads and says picks are hidden until the deadline.

**Blocked by:** 32: Followed leagues, Gameweek-final job and `/league`

**Status:** ready-for-agent

- [ ] `/rivals` lists at most 3 qualifying Footballers per side against the nearest ±2 Rivals, with the captain-share line.
- [ ] `/rivals all` uses the whole Goal league and says how many Rivals.
- [ ] A Member with Overall rank as Goal gets Rivals from their Followed league.
- [ ] A head-to-head opponent is treated as one Rival.
- [ ] Differences under 0.35 pts a Gameweek are hidden; with none qualifying, it says no single Footballer stands out.
- [ ] No summed net edge appears anywhere.
- [ ] Between deadlines the caveat appears.
- [ ] Rival picks for a league are deleted once no Member follows it.
- [ ] Nothing is pushed: Gaps appear only in reply to a command.
