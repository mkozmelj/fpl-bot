# 28: Join flow, settings and `/leave`

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** the full conversation for joining, changing settings and leaving, as approved in ticket 14. The pure bot module in [the prototype](../prototypes/14-telegram-flow-PROTOTYPE.html) is the reference and encodes the state machine more precisely than prose: read it first. Its key decisions:

- Setup asks for whatever is still missing, in order: team ID, then Goal, then (for Mini-league) the league, then timezone. When nothing is missing a joining Member becomes active and sees a summary plus the command list.
- Steps: `team_id`, `confirm_team`, `goal`, `league`, `tz`, `tz_text`, `watch_pick` (ticket 29), `confirm_leave`.
- Any `/command` clears the open step and pending data. A joining Member who sends any command other than `/start` or `/leave` is told "Let's finish setting you up first" and re-asked.
- Each keyboard is tied to the message that showed it; a button press whose message is not the chat's latest keyboard is ignored with "That button is out of date. Send /help to see what you can do."

Where the prototype and later decisions differ, later decisions win: strangers get silence (ticket 16), not the prototype's "invite-only" reply.

Linking looks up the team on FPL through the sources adapter (entry and its leagues).

**Blocked by:** 26: Walking skeleton: invite and redeem

**Status:** resolved

- [ ] Sending a team ID shows team name, manager and overall rank with "Is that you?" buttons; non-digits and unknown IDs get the prototype's replies; "No" asks again.
- [ ] A team already linked to another Member is refused ("ask the owner").
- [ ] Goal by buttons. Mini-league lists the team's private leagues to pick from; with none, the Goal falls back to Overall rank with an explanation.
- [ ] Timezone by four buttons or "Other…" then a typed city or IANA zone; an unknown city is rejected politely.
- [ ] `/start` resumes an abandoned setup; any command abandons the open question; stale buttons are ignored and change nothing.
- [ ] `/help`, `/settings` (everything stored about the Member), `/goal` and `/tz` work for active Members; switching Goal mid-season works.
- [ ] `/time HH:MM` sets the Price alert time (default 20:00 local); invalid times are rejected; when the time falls outside 17:00-23:15 UK it says so and states the real send time.
- [ ] `/leave` asks once; confirming hard-deletes the Member and everything tied to them; the invite stays used, so the old code cannot rejoin. Test asserts the Member rows are gone.
- [ ] Tests through the seam mirror the prototype walkthroughs: happy path, wrong team ID, same team twice, button tapped twice, no mini-league, typed timezone, leaving, abandoned setup.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 06991a2; review fix-ups in 1004dd3). Tests live in `core/tests/`.
