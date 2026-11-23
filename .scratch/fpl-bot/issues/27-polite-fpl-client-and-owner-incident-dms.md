# 27: Polite FPL client and owner incident DMs

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** every request to FPL goes through one polite client, and the owner hears about trouble exactly once per incident. Behind the sources adapter from ticket 26:
- One shared rate limiter for all FPL traffic, at most 1 request a second, with priorities: interactive commands and the Price alert first, the Elite sampler last.
- One generic browser-style User-Agent with no personal details, URL or repo name. Conditional requests (ETag / Last-Modified) where FPL supplies them.
- 429 and 5xx: exponential backoff with jitter, honouring Retry-After, at most 5 tries. 403: never retried; the calling job pauses until its next scheduled run and the owner is told.
- FPL's "game is being updated" answer is recognised as its own outcome (ticket 31 waits on it; those waits are not backoff tries).
- `bootstrap-static` is held in memory only, never stored raw, and refetched on demand when more than 15 minutes old.
- An owner notification service: one Telegram DM per job and failure type, carrying a short fixed code (no stack trace, no Member details); at most one reminder every 6 hours while it persists; one "recovered" DM when it clears. A DM goes out on a 403, or on the second failure in a row.

**Blocked by:** 26: Walking skeleton: invite and redeem

**Status:** ready-for-agent

- [x] Through the seam with a fake clock: a burst of FPL-bound work never exceeds 1 request a second, and interactive work overtakes queued low-priority work.
- [x] A 429 with Retry-After is retried after that delay; a 5xx is retried with growing jittered delays and gives up after 5 tries.
- [x] A 403 is never retried and produces exactly one owner DM with a fixed code; the next run of that job that succeeds produces one "recovered" DM.
- [x] A second consecutive failure of a job DMs the owner; a third does not DM again within 6 hours.
- [x] Every outgoing request carries the generic User-Agent and nothing identifying.
- [x] Raw FPL responses are never written to the database.
- [x] Fixtures exist for 503 "updating", 403, 429 and missing fields.
