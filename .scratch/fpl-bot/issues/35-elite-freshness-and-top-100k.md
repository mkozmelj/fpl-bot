# 35: Elite freshness and the top 100k cohort

**Parent:** [25: Spec, Phase 1](25-spec-phase-1.md)

**What to build:** Elite figures stay honest when the sampler doesn't finish, and Members can compare against the top 100k too.
- The sampler also covers the top 100k as a separate cohort at ±2%. Both cohorts together are roughly 4,400 requests (about 73 minutes) a Gameweek.
- Partial run: if each cohort reached at least half its target, publish it with the margin of error recomputed and labelled "partial sample". Otherwise keep the previous Gameweek's figures, shown with a warning naming their Gameweek. The two are never mixed.
- If the cohort standings finish only after the first kickoff, the cohort is still used and the run is marked "read late".
- The sampler yields to interactive commands and the Price alert, and resumes.
- Command: `/gap 100k` (and `/gap 100k captain`); plain `/gap` stays the top 10k.

**Blocked by:** 34: Elite gap, top 10k, full sample

**Status:** resolved

- [ ] `/gap 100k` shows the top 100k cohort with its own sample size and margin of error.
- [ ] A partial-sample fixture produces a "partial sample" label and a larger margin of error.
- [ ] A sample below half its target leaves last Gameweek's figures in place with a "Using GWn figures" warning; current and previous figures are never combined.
- [ ] A late standings read is marked "read late" and still used.
- [ ] A Member command sent during a sampler run is answered without waiting for the sampler.
- [ ] Re-running the job for a completed Gameweek is a no-op; startup catch-up resumes a missing `elite` row.

## Answer

Implemented on the integration branch `spec-25-phase-1` (merged in 0b4cd41; review fix-ups in 1004dd3). Tests live in `core/tests/`.
