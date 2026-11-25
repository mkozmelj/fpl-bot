# 39: Nightly encrypted Member backup

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** the owner has an off-platform backup of the small, irreplaceable tables (ticket 23). Every night the bot exports only the Member and config tables (Members, invites, Watch lists, Goals), encrypts the export with `age` against a public key from config, and sends it as a document to the owner's Telegram chat, keeping the last 7. The large tables rely on Neon's restore window and the backfill. The restore drill goes in the runbook (ticket 41).

**Blocked by:** 29: Watch list

**Status:** resolved

- [ ] At the nightly tick the owner receives one encrypted document; decrypting it with the matching private key yields the Member tables.
- [ ] The export contains nothing beyond the Member and config tables.
- [ ] Without a public key configured, the backup is skipped and the owner is told once.
- [ ] Older backup messages beyond the last 7 are removed from the chat.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 61670c8; review fix-ups in 1004dd3). Tests live in `core/tests/`.
