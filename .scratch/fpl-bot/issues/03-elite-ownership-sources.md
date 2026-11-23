# Where to get top-1k / 10k / 100k ownership data

Type: research
Status: resolved
Blocked by: —

## Question

Which free sites or datasets already publish **Elite ownership** (ownership, captaincy and chip usage among the overall top 1k / 10k / 100k), and can we legally pull it?

Look at, for example, LiveFPL, FPL Statistics, FPL Review's free tier, Fantasy Football Fix, FFHub, the official FPL "top managers" figures, and community GitHub datasets. For each source, record:
- which cohorts it covers
- how often it updates
- the access method
- ToS position

If none is usable, design the fallback: sample Squads from the official API's league standings (how many per cohort for a ~1–2% margin of error, request count, and time needed to stay under rate limits).

Findings go in `.scratch/fpl-bot/research/03-elite-ownership-sources.md`.

## Answer

- No free source publishes usable Elite ownership with permission. The official API gives only overall-game figures: `selected_by_percent`, `most_captained` and `chip_plays`. It has no top-N cohorts.
- LiveFPL is the only free machine-readable source. Its public `livefpl.us` JSON gives:
  - effective ownership for the full top 10k
  - captaincy and chips for the top 100, 1k and 10k (full counts) and for the top 100k (from only a 1,000-manager sample, about ±3.1%)

  It updates several times a day, but has no ToS, no API and no licence. Use it as a dev cross-check only, unless its author agrees.
- Fantasy Football Hub (cl. 6.6 bans scraping, even for personal use), Fantasy Football Fix (tiered data is Premium, and s.11 forbids reproduction) and FPL Review (fixed "Elite 1000", not the top 10k or 100k; export is Patreon) are not usable. FPL Statistics was unreachable. No GitHub dataset has cohort ownership.
- Decision: build our own sampler on the official API. One post-deadline job per GW reads league 314 standings (use `rank_sort`) and Squad picks. Picks give ownership, captaincy and `active_chip` in one call, and they are 404 until the deadline.
- Sample sizes at ±2% worst case, 95% confidence: about 1,940 for the top 10k and about 2,350 for the top 100k. With a stratified design that is about 4,400 requests per GW, or about 24 minutes at 3 req/s. ±1% costs about 14,100 requests (about 78 minutes). A top-1k census adds about 1,020 requests.
- Legal caveat for the whole bot: FPL T&C 2026/27 cl. 28(d) forbids "automated systems to access the Game and extract information", and cl. 29 claims "any Game data". Mitigate with low volume, caching, no login and non-commercial use.

Findings: [../research/03-elite-ownership-sources.md](../research/03-elite-ownership-sources.md)
