# Telegram flow for joining and the Phase-1 commands

Type: prototype
Status: resolved
Assignee: owner
Blocked by: 01

## Question

How should a friend join and use the bot in Telegram for Phase 1? Prototype the conversation:
- invite-only access (an invite code or an allow-list?)
- linking an FPL team ID, with a confirmation that shows their team name
- choosing a Goal and a mini-league
- managing the Watch list
- setting the Price alert time and timezone (default 20:00 local)
- seeing their Squad, their Rivals and their Elite gap
- leaving and deleting their data

Link the prototype as an asset.

## Answer

Resolved with the owner, 2026-11-19: they tried the prototype and approved the flow as built. The logic module in the prototype is the reference for the Phase-1 spec.

## Prototype

[Telegram join-flow simulator](../prototypes/14-telegram-flow-PROTOTYPE.html): a single HTML file, double-click to open. It has a pure bot module (portable) and 11 walkthroughs for the awkward cases.

Design choices it puts up for reaction:
- Invite: owner-only `/invite` makes a single-use code and a `t.me/…?start=CODE` link. Redeeming allow-lists the chat at once, so an abandoned setup resumes with `/start`. Cap of 10 Members.
- Link: Member sends a team ID, the bot shows the team name, manager and rank, and asks "Is that you?". A team already linked to another Member is refused.
- Goal: inline buttons. Mini-league lists the team's private leagues; with none, it falls back to Overall rank.
- Timezone: four buttons plus "Other…" (typed city or zone). Alert time defaults to 20:00 local and changes with `/time HH:MM`.
- Any command abandons the current question; old buttons are ignored with a polite message.
- `/leave` asks once, then deletes the Member record; the invite stays used.
