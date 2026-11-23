# How the best FPL managers make decisions in 2026

Type: research
Status: resolved
Blocked by: —

## Question

What methods do consistently top FPL managers use now, and what is the current consensus on the strategy that maximises overall rank?

Cover:
- Expected-points models and solvers (FPL Review-style EV, multi-Gameweek planning horizons, decaying weights).
- Rolling and banking free transfers, and when hits pay off.
- Template versus differentials, and effective ownership in captaincy.
- Team value and price-change chasing.
- Bench order and which positions to leave on the bench.
- How overall-rank strategy differs from mini-league strategy (risk when you're behind or ahead).

Prefer primary sources: content from high-ranked managers with verifiable FPL history, solver authors' write-ups, and published analyses. Separate what is evidence from what is folklore.

Findings go in `.scratch/fpl-bot/research/05-elite-manager-methods.md`.

## Answer

- Elite consensus for the Overall rank Goal is to maximise multi-Gameweek Expected points: a 6–8 GW horizon with decay of 0.85–0.9 (FPL Review and Sertalp Bilal solver defaults), used as "a source of information" with judgement on top. The last three champions plan about 5–6 GWs ahead and none follows a solver blindly.
- Rolling an FT has a small option value that falls as FTs bank: about 2.0 / 1.6 / 1.3 / 1.1, and 0 at the 5-FT cap that still applies in 2026/27. A used transfer is worth about 5–6 points over its lifetime.
- Hits are rare at the top. The most common 2025/26 Top-50 hit count was 0, and solvers default to `weekly_hit_limit: 0`. Take a -4 only when the decayed horizon gain clearly beats 4 points plus the forgone FT value plus model noise.
- Captain on xP and use EO only as a tiebreaker (FPL Review Risk Position defaults to 0, ±0.15). Keep a template-heavy core with a few reasoned differentials. Differentials add variance, not edge.
- Team value is worth about 20 points per £1m per season, declines through the season, and never justifies a hit. Bench weights (S1 about 0.2–0.3, S2 about 0.06–0.1, S3 about 0.01) mean the bench should be minimal and ordered by the chance each player is needed.
- Luck dominates single seasons (r ≈ 0.42 season to season; only about 30% repeat top 10k), so the bot should score its advice on xP, not on outcomes.
- For the Mini-league Goal, swap Elite EO for Rival EO. Shield (copy Rivals) when ahead, and add 2–4 high-variance differentials or a captain different from the leader's when behind. Drive the choice with a win-probability simulation.
- Full findings and decision playbook: [../research/05-elite-manager-methods.md](../research/05-elite-manager-methods.md)
