# 32: Followed leagues, Gameweek-final job and `/league`

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a Member sees how they're doing in the league they care about.
- Followed leagues per Member: every Mini-league with at most 50 managers (de-duplicated across Members) plus the head-to-head opponent each Gameweek. A Goal league above 50 is followed as its top 10 plus the 20 managers directly above and 20 directly below the Member. They are recomputed on join, on Goal change and after each Gameweek.
- The Gameweek-final job runs once a Gameweek is `finished` and `data_checked`: it refreshes each Member's history and each Followed league's standings, and writes a `gw_final` completion row. (Ticket 33 adds `event/{gw}/live` to the start of this job.)
- `/league` shows the Goal league (the Followed league when the Goal is Overall rank): the table with rank movement arrows, points behind the Rival directly above, points ahead of the Rival directly below, and the gap to the leader. No Ghost Squad row in Phase 1. Shape follows `leagueMessage` in [the Gap prototype](../prototypes/19-gap-views-PROTOTYPE.html).

**Blocked by:** 31: Post-deadline picks job, scheduler and startup catch-up

**Status:** ready-for-agent

- [ ] `/league` renders the table with ▲/▼/– movement, the "you" marker, the two gap lines and the leader line.
- [ ] A Member who is top or bottom gets only the lines that apply.
- [ ] A Goal league with more than 50 managers shows only the followed subset, and says so.
- [ ] After the Gameweek-final tick, `/league` reflects the new standings; re-running the job is a no-op.
- [ ] A league no Member follows any more stops being refreshed.
