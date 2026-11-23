# 38: `/status`, heartbeat and the `ready sha=` log line

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** the owner can see the bot's health from Telegram, and outside monitoring can tell it's alive (ticket 23).
- Owner-only, read-only `/status`: uptime and deploy version, the last completion of each job (`price_archive`, `picks`, `elite`, `gw_final`), whether Neon is reachable, and Neon storage if readable without an extra key.
- A ping every 5 minutes to an optional `HEARTBEAT_URL`, only while the event loop and scheduler are healthy. It never touches the DB and carries no Member data. No URL set, no ping.
- Once migrations, the Telegram poll and the scheduler are up, log exactly `ready sha=<commit>`, and DM the owner "online vX".
- A one-time owner DM when Neon storage passes 70% or compute hours pass 80% of the month, if readable without a key; otherwise skipped.

**Blocked by:** 27: Polite FPL client and owner incident DMs; 31: Post-deadline picks job, scheduler and startup catch-up

**Status:** ready-for-agent

- [ ] `/status` from the owner shows the fields above; from anyone else, nothing.
- [ ] With `HEARTBEAT_URL` set and a fake clock, a ping goes out every 5 minutes; with the scheduler stopped, pings stop.
- [ ] The `ready sha=` line and the "online" DM appear once at startup.
