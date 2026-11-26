# 54: Regex Scout overrides and the shadow comparison

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** team news turned into minutes adjustments at no cost, plus the measurement that decides whether Claude-derived overrides may ever count.
- A pure regex parser from FPL's templated news text (injury with a percentage, suspended until, expected back, loan or left the club, and similar) and `status` into overrides on start probability and minutes-if-started. Unparsed lines are returned separately as leftovers. Check whether FPL's `scout_risks` and `scout_news_link` fields exist and add them if they parse cleanly.
- Every xP run applies the regex overrides (live from day one). Overrides are stored per season, Gameweek and Footballer with source `regex`.
- Shadow: the deadline −90 run stores xMins and xP three ways (no overrides, regex, regex plus Claude). Once the Gameweek is final, all three are scored against actual minutes and points. These are aggregates of the bot's own predictions, not Member data.
- A setting `claude_overrides_live`, off by default, that the owner turns on by hand only once Claude-derived overrides beat no overrides on minutes MAE over at least 8 Gameweeks with at least 30 affected Footballer-Gameweeks.

**Blocked by:** 49: xP job, storage and `/status`

**Status:** open

- [ ] A table of real recorded FPL news strings maps to the expected overrides; unknown wording is returned as a leftover.
- [ ] A Footballer flagged suspended gets 0 xMins for the suspended Gameweeks.
- [ ] Shadow rows are written at deadline −90 and scored after `gw_final`; a rerun doesn't duplicate them.
- [ ] With `claude_overrides_live` off, no Claude-derived override changes any advice.
