# 44: Phase 1 review leftovers

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** clear the Phase 1 code-review items that sit in files Phase 2 extends, before Phase 2 tickets start editing them. No change Members can see.
- Split `delivery/member_flow.py` by concern (join flow, settings, leave) and `sources/fpl.py` (polite client and transport; endpoint parsing; data types), keeping the public names the rest of the code imports.
- Key the Watch list on the Member number instead of `chat_id`, with a backward-compatible migration.
- Replace the "optional, not used in Phase 1" `ANTHROPIC_API_KEY` wording in `docs/runbook-secrets.md` and `.env.example` with "optional; enables `/why` prose and Scout leftovers (Phase 2)".

**Blocked by:** None (can start immediately)

**Status:** open

- [ ] `member_flow.py` and `sources/fpl.py` are split; no module over roughly 400 lines remains in either area.
- [ ] Watch list rows reference the Member number; the migration moves existing rows and runs in Railway's pre-deploy step without downtime.
- [ ] `/leave` still removes the Watch list; Price alert rises for Watch-list Footballers are unchanged.
- [ ] Runbook and `.env.example` describe `ANTHROPIC_API_KEY` for Phase 2.
- [ ] The existing test suite passes unchanged apart from imports; ruff and pyright are green.
