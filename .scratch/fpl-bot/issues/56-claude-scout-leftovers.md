# 56: Claude Scout leftovers

**Parent:** [43: Spec, Phase 2](43-spec-phase-2.md)

**What to build:** the once-a-Gameweek shared job that sends Claude only the news lines the regex couldn't parse.
- Runs at deadline −90 minutes, right before the xP run, only if there are leftovers changed this Gameweek. One synchronous call; the input is Footballer ID, name, club and news text, nothing else.
- Output must parse against the strict schema: a list of {Footballer ID from the input, minutes-if-started change, start-probability change, confidence low/medium/high}. Anything else is dropped and logged as a count. No retry.
- Parsed overrides are stored with source `claude` and feed the shadow from ticket 54. They change advice only when `claude_overrides_live` is on.
- Completion row `scout` per Gameweek. `/status` shows this Gameweek's leftover count.

**Blocked by:** 54: Regex Scout overrides and the shadow comparison; 55: Claude adapter, guardrails and `/why`

**Status:** open

- [ ] No leftovers means no Claude call.
- [ ] A reply naming a Footballer ID not in the input, or failing the schema, is dropped entirely.
- [ ] With no API key the job completes and records zero Claude overrides.
- [ ] Claude overrides appear in the shadow's third column and not in advice while the setting is off.
- [ ] The job runs once per Gameweek; a rerun makes no second call.
