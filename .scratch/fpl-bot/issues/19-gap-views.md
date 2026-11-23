# Elite gap, Rival gap and the mini-league progress view

Type: prototype
Status: resolved
Assignee: owner
Blocked by: 13

## Question

Given the data ingestion now settled in [Which data the bot collects, how often, and what it keeps](13-data-ingestion-design.md), how are the **Elite gap** and the **Rival gap** computed and shown in Telegram, and what does the mini-league progress view look like?

- **Phase 1 has no xP yet.** What stands in for "weighted by how much the difference could swing points": ownership × price, recent points, form, or something else? How does it switch to xP in Phase 2?
- **Which Elite ownership measure drives the Gap:** 15-man ownership, XI share, captain share or EO? How are the margin of error, a partial sample and a stale (previous Gameweek) figure shown?
- **Rival gap:** over one Followed league or all of them, and against all Rivals or only the ones near the Member's rank. The head-to-head opponent as a special case.
- **Timing:** Gaps exist only after a deadline (picks are hidden before). What does a Member see between deadlines?
- **The mini-league progress view:** rank movement, the points gap to the Rivals above and below, and the Ghost Squad as a Rival later on.

Link the prototype as an asset.

## Assets

- Prototype (in progress, awaiting owner reaction): [19-gap-views-PROTOTYPE.html](../prototypes/19-gap-views-PROTOTYPE.html)
  - Proposed defaults it embodies: edge = (you start − reference XI share) × weight + (you captain − reference captain share) × weight, in points per GW; weight = form (Phase 1) or xP (Phase 2); XI share and captain share as the Elite measure; differences under 2× the margin of error or 0.35 pts/GW hidden; Rival gap over nearest ±2 by rank (or `all`) in the Goal league, H2H as a single opponent; between deadlines the last-deadline Squad with a caveat; partial, stale and not-ready Elite figures labelled, never mixed; league table with movement arrows, gaps above and below, Ghost Squad as one row.

## Answer

Approved as prototyped by the owner, 2026-11-20 ([prototype](../prototypes/19-gap-views-PROTOTYPE.html)).

- **Edge per Footballer:** (you start − reference XI share) × weight + (you captain − reference captain share) × weight, in points per Gameweek against the reference group.
- **Weight:** recent form (average points over the last 4 finished Gameweeks) in Phase 1; xP for the next Gameweek in Phase 2. Same formula, only the weight changes.
- **Elite measure:** XI share and captain share. 15-man ownership and EO are not used. `/gap captain` shows the captain part on its own, since captaincy dominates the combined number.
- **What is listed:** at most 3 Footballers each side ("you back, they mostly don't" and "they back, you don't"). A difference is hidden if it is under 2× the margin of error or under 0.35 pts a Gameweek. If nothing qualifies, the bot says the Member looks like the template.
- **No net total:** a summed "net edge" is not shown; it is misleading when the Footballer pool is incomplete.
- **Freshness:** the header shows Gameweek, sample size and margin of error. A partial sample is labelled; a previous-Gameweek figure carries a warning; with no figures yet the bot says so and points to `/rivals`. They are never mixed.
- **Rival gap:** runs over the Goal league (or the Followed league when the Goal is Overall rank). The default is the nearest 2 Rivals above and 2 below by rank; `/rivals all` uses everyone. A head-to-head opponent is a single Rival, and the captain line shows how many Rivals share the Member's captain.
- **Between deadlines:** the last-deadline Squad is used and the message says GW picks are hidden until the deadline. No push messages; Gaps are on demand only.
- **League view (`/league`):** table with rank movement arrows, points behind the Rival above and ahead of the Rival below, and the gap to the leader. The Ghost Squad appears from Phase 4 as one extra row with no commentary.
- **Prototype capture:** this folder is not a git repository, so the HTML stays in `prototypes/` as the primary source.
