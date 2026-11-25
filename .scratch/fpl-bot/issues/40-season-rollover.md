# 40: Season rollover

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** a new FPL season starts cleanly, and only when the owner says so (ticket 23). The bot never rolls over by itself.
1. It detects the new season (`bootstrap-static` shows GW1 and different IDs).
2. It pauses Price alerts and advice commands, which say a new season is being set up.
3. It DMs the owner a checklist.
4. Owner-only `/rollover` asks for confirmation, then keeps last season's aggregates under their season key, clears Rival picks, Followed leagues and Member and Rival history, and keeps Members (team ID, chat, timezone, alert time).
5. Each Member is asked once to reconfirm their Goal and league with the ticket 28 flow.

**Blocked by:** 33: Rival gap (`/rivals`); 37: Price archives and `/accuracy`

**Status:** resolved

- [ ] A new-season fixture pauses alerts and advice and DMs the owner a checklist once.
- [ ] `/rollover` needs confirmation and is refused for anyone but the owner.
- [ ] After rollover, Members still exist, Rival data is gone, last season's aggregates are still queryable by season, and each Member gets one Goal reconfirmation prompt.
- [ ] Running `/rollover` twice does nothing the second time.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 1c82e50; review fix-ups in 1004dd3). Tests live in `core/tests/`.
