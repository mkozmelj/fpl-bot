# 57: `/note`: a Member's own team news

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** a Member can paste team news that affects only their own advice.
- `/note <text>`: at most 500 characters and 3 per Member per Gameweek. The text plus a list of candidate Footballers (no Member ID) goes to Claude with the Scout schema. The parsed result is stored as a per-Member overlay that expires at the next deadline.
- `/note` alone lists active notes; `/note clear` removes them.
- Notes count as Claude-derived: while `claude_overrides_live` is off, the reply says the note is recorded for testing and doesn't change advice yet. When on, `/captain`, `/bench`, `/gap` and `/rivals` for that Member are recomputed with the shared table plus the overlay.
- Notes never enter the shared job and are never logged. They are deleted on `/leave`, cleared at rollover and included in the encrypted Member backup.
- With no API key, `/note` says notes aren't available on this bot.

**Blocked by:** 54: Regex Scout overrides and the shadow comparison; 55: Claude adapter, guardrails and `/why`

**Status:** open

- [ ] Length and per-Gameweek limits are enforced with a polite reply.
- [ ] A note expires at the next deadline.
- [ ] Another Member's advice is unchanged by a note (isolation test).
- [ ] The "testing only" reply appears while the setting is off; advice changes when it is on.
- [ ] `/leave` deletes notes and overlays; the backup includes them.
- [ ] The captured Claude prompt carries no Member identifier.
