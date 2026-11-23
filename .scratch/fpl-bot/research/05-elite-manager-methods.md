# How the best FPL managers make decisions (2026/27)

Research for ticket `05-elite-manager-methods`. Written 2026-11-19, around Gameweek 12 of 2026/27. Terms follow `GLOSSARY.md`.

Each claim is tagged:
- **[E] Evidence**: a primary or quantitative source, such as solver code or docs, a published analysis, or a peer-reviewed paper.
- **[P] Practice**: what verifiable elite Managers say they do, taken from interviews and their own columns. This is real, but it comes from individuals and small samples.
- **[F] Folklore**: widely repeated advice with no measurement behind it.
- **[I] Inference**: my own reasoning from the above. It is not sourced.

---

## TL;DR

1. **The modern core is to maximise multi-Gameweek Expected points (xP) and use judgement on top.** Solver authors write the objective as a decayed sum of xP over a 6–8 Gameweek horizon. FPL Review's defaults are horizon 6, decay 0.85 and FT value 1.75. Sertalp Bilal's open-source solver defaults to horizon 8 and decay 0.9. Elite Managers, including the last three overall winners, say they plan roughly 5–6 Gameweeks ahead and treat models as "a source of information", not as orders. [E][P]
2. **Rolling a free transfer has a small, state-dependent value, and it shrinks as transfers bank up.** The open-source solver values the rolls at 2.0 (1→2 FT), 1.6, 1.3 and 1.1 (4→5). FPL Review suggests about 2.0 as a baseline. At 5 FTs, the cap that still applies in 2026/27, rolling is worth nothing, because the extra transfer is lost. [E]
3. **Hits are rare among top Managers and are switched off by default in solvers.** The open-source solver ships with `weekly_hit_limit: 0`. The most common hit count among the 2025/26 Top 50 was zero, and very few took more than six. FFScout's tracked experts averaged about 2 hits each in 2025/26. A hit is justified only when the decayed xP gain over the horizon clearly exceeds 4 points plus the FT value given up. [E][P]
4. **Pick the captain with the highest xP, and use effective ownership (EO) only as a tiebreaker.** FPL Review's "Risk Position" setting (EV × EO) defaults to 0, with a recommended range of ±0.15. Champions describe picking "the highest expected value" captain, which is usually the template one. [E][P]
5. **Template versus differential is a question of variance, not of edge.** Top-tier Squads are measurably more alike than average ones. A differential gains rank only if it outscores the popular alternative. For the Overall rank Goal the consensus is a template-heavy core with a few deliberate differentials. [E][P]
6. **Team value is worth about 20 points per £1m over a whole season, and that value declines as the season goes on.** It never justifies a hit (a FFScout model, 2019; a correlational academic result of 21.8 points per £1m at Gameweek 19). Solvers value cash in the bank at only about 0.08–0.10 points per £1m. Elite Managers split on price chasing: some transfer early to catch rises, others transfer late for team news. [E][P]
7. **The bench should be cheap and ordered by the chance each player is actually needed.** Solver bench weights put Sub 1 at roughly 0.2–0.3, Sub 2 at 0.06–0.1, Sub 3 at 0.002–0.03 and the backup goalkeeper at 0.03. In other words, bench points are worth very little outside Bench Boost weeks. [E]
8. **Luck is huge, so judge the process, not single results.** The season-to-season correlation of points is about 0.42. Even Managers with 4+ prior top-10k finishes have only about a 30% chance of repeating. Champions are largely lucky outliers: Erik Ibsen won 2025/26 in his first season. Advice should be judged on xP, not on realised points. [E]
9. **The Mini-league Goal differs in the reference group and in risk appetite.** Use your Rivals' EO instead of global or Elite EO. When behind, add variance relative to Rivals: in one simulation, two high-variance differentials overturned a 20-point deficit over seven Gameweeks 32% of the time, against 22% for safe picks. When ahead, copy ("shield") your Rivals' key picks and captain. Daily-fantasy research shows that modelling opponents' picks multiplies returns in winner-takes-most contests. [E][I]

---

## 1. Detailed findings

### 1.1 Expected-points models and solvers

**What solvers optimise** [E]
- FPL Review's solver and Sertalp Bilal's open-source `FPL-Optimization-Tools` both formulate FPL planning as a mixed-integer linear programme solved with HiGHS. The objective is a decayed sum of projected points over a multi-Gameweek horizon, with extra terms for FTs held, money in the bank and bench points. https://docs.fplreview.com/the-model/solvers/solver-comparison/ , https://github.com/sertalpbilal/FPL-Optimization-Tools
- **FPL Review defaults** (https://docs.fplreview.com/the-model/solvers/settings/):
  - Transfer Depth: 6 Gameweeks, recommended to be "a couple of GWs short of loaded Projection Horizon".
  - Time Decay: 0.85, recommended range 0.80–0.95.
  - FT Value: 1.75, with about 2.0 cited as the common baseline. A higher value makes the solver more patient, a lower one greedier.
  - Bank Value: 0.10 points per £1m, range 0–0.20.
  - Sub Weight: 1.00.
  - Risk Position: 0, with a recommended range of -0.15 to +0.15. It is labelled experimental.
  - Future Info Value: 0. This is an optional bonus for waiting on information such as confirmed blank or double Gameweeks.
  - Linear Optimiser weights: vice-captain 0.05, backup goalkeeper 0.03, Sub 1 0.30, Sub 2 0.10, Sub 3 0.03.
- **Sertalp Bilal defaults**, from `data/comprehensive_settings.json` and `data/README.md` (https://raw.githubusercontent.com/sertalpbilal/FPL-Optimization-Tools/main/data/README.md , https://raw.githubusercontent.com/sertalpbilal/FPL-Optimization-Tools/main/data/comprehensive_settings.json):
  - `horizon` 8 and `decay_base` 0.9, which works out to a 10% discount per Gameweek.
  - `ft_value_list` {2: 2.0, 3: 1.6, 4: 1.3, 5: 1.1} and `ft_value` 1.5.
  - `ft_use_penalty` 0.2, which stops the solver scheduling trivial transfers.
  - `bench_weights` {GK 0.03, S1 0.21, S2 0.06, S3 0.002} and `vcap_weight` 0.1.
  - `itb_value` 0.08 per £1m.
  - `weekly_hit_limit` 0 and `hit_cost` 4.
  - `no_transfer_last_gws` 2, so no transfers are planned in the last 2 horizon Gameweeks. Transfers there would be judged on truncated value.
  - `xmin_lb` 300 expected minutes, which drops low-minutes Footballers.
  - A `randomized` option that adds noise so the solver produces several different robust plans.
- FPL Review warns that differences of about 0.5 EV over a 12-Gameweek horizon "hold little meaning". Small gaps should not drive decisions. https://docs.fplreview.com/the-model/projections/expected-value/
- FPL Review frames solvers as tools for testing how robust a decision is "across parameter uncertainty" and for scenario planning, not as oracles. https://docs.fplreview.com/the-model/solvers/into-to-solvers/
- A 2025/26 peer-reviewed-style framework (arXiv 2505.02170) found that robust MILP variants did not uniformly beat deterministic ones. That suggests no model is fully trustworthy. https://arxiv.org/abs/2505.02170

**What elite Managers say** [P]
- **Jonas Sand Låbakk**, 2023/24 champion: "I try to use analytics as a source of information and not take things overly prescriptively." He uses analytical models but no named solver. https://www.fantasyfootballscout.co.uk/2024/05/27/an-interview-with-fpl-2023-24-champion-jonas-sand-labakk/
- **Lovro Budišin**, 2024/25 champion: "For me, the eye test comes first", with stats second. He talks choices through with friends and content creators. https://fpl.page/article/an-interview-with-lovro-budisin-fpl-world-champion
- **Erik Ibsen**, 2025/26 champion in his first season: "heavy on stats" (xG, form), plans "5-6 Gameweeks ahead", and keeps "fixed" and "flexible" slots in his Squad. https://allaboutfpl.com/2026/03/interview-with-world-number-1-fpl-manager-erik-ibsen-2025-26/
- I found no interview with a verifiable multi-season elite Manager that describes following a solver mechanically. Solver use is widespread in the analytics community, but in public, elite Managers present it as one input among several. [I]

### 1.2 Rolling and banking free transfers; when hits pay off

**Rules that apply now** [E]
- You can roll up to 5 FTs in 2026/27. The December AFCON bonus FTs from 2025/26 are gone. https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627
- Since 2024/25, saved FTs are no longer reset when you play a Wildcard or Free Hit. https://www.premierleague.com/en/news/4059225 , https://www.premierleague.com/en/news/4058895

**How much a roll is worth** [E]
- The open-source solver values rolls on a declining scale: 2.0 (1→2), 1.6 (2→3), 1.3 (3→4), 1.1 (4→5). Holding a fifth FT has no roll value, because a sixth cannot be banked. Source: the solver README above.
- FPL Review puts the FT value around 1.75–2.0 and has a separate "Burn FT Value" setting, recommended equal to the FT value. https://docs.fplreview.com/the-model/solvers/settings/
- **An important distinction.** The FT value of about 2 points is the option value of keeping a transfer for later. It is not what a transfer is worth when used. FPL Theorist's PGLT analysis puts a well-used transfer at about 6 points over its lifetime: 200 points needed from transfers divided by 34 FTs. With 16 hits added, the target falls to about 5.3. He gained about 5.37 per transfer in 2020/21. https://www.fantasyfootballscout.co.uk/2021/10/08/points-gained-over-the-lifetime-of-a-transfer [E, one Manager's data]

**Hits** [E][P]
- Solver defaults: `weekly_hit_limit: 0` (open source). FPL Review has no hit-cost setting, because hits are simply -4 in the objective.
- The most common outcome among the 2025/26 Top 50 was no hits. Many took one or two, and very few took more than six. The All-Time Top 50 spread more widely, taking up to 10. Hits spiked in Gameweek 38. https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/
- FFScout's tracked experts in 2025/26 averaged 2 hits each. The most anyone took was 4 (-16). https://www.fantasyfootballscout.co.uk/2026/06/02/who-finished-1st-in-fpls-the-great-and-the-good
- Låbakk took -12 all season and grew more risk-averse. Budišin tries to "avoid taking too many point hits". Sources as in 1.1.
- Zophar (Utkarsh Dalmia, eight top-10k finishes) said in an older column that his rare hits usually come "in combination with two free transfers". In 2025/26 he was rolling transfers toward fixture swings. https://www.fantasyfootballscout.co.uk/category/pro-pundits-zophar/ (the column archive; the specific pieces were surfaced via search)
- FFScout's 2019 value study gives a rule of thumb: making £1m of team value takes about 10 transfers, so building it through hits costs about 40 points to gain about 20. https://www.fantasyfootballscout.co.uk/2019/09/12/the-value-of-team-value/

**Folklore** [F]
- "Never take hits." The evidence says rarely, not never. Hits made alongside FTs, or to replace a 0-xP starter with no bench cover, are the common elite exceptions.
- "Always roll in Gameweek 1–2." There is no data behind this. The solver logic is simply that rolling wins when no move gains more than the state-dependent FT value.

### 1.3 Template versus differentials, and effective ownership in captaincy

**Evidence** [E]
- Squad similarity rises with tier: top-tier Managers' Squads are more alike, even before Gameweek 1. Herding comes and goes over the season. O'Brien, Gleeson & O'Sullivan (Univ. of Limerick), arXiv 2009.01206. https://arxiv.org/abs/2009.01206
- The same paper found that higher-tier Managers make better transfer choices and score more from their captains.
- Most transfers-in by the 2025/26 Top 50 were of Footballers under about 20% overall ownership, clustered around 0–15%. Elite Squads therefore differ from the global template while converging with each other. https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/
- FPL Review approximates risk as EV × EO against a reference sample, with a Risk Position default of 0 and a ±0.15 band. https://docs.fplreview.com/the-model/solvers/settings/ , https://docs.fplreview.com/the-model/projections/expected-value/
- EO is ownership plus captaincy share plus triple-captaincy share. A Footballer with EO above 100% costs you rank when he scores if you don't own and captain him. https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions
- Captaincy carries a large share of points: 29.1% of Budišin's 2024/25 points came from captains. https://www.premierleague.com/news/4322425

**Practice** [P]
- Seb Wassell: decide which Footballer will score most first, and use EO only to break ties. Use differentials for specific reasons such as fixture swings or form shifts, not for their own sake. Source as above.
- Låbakk: "Boring picks are good." He captains the highest-EV option, which is usually the template captain.
- Ibsen sometimes prefers a safe 7–8 points to a 20-point punt, and calls his own style "almost passive".
- In 2025/26 FFScout's tracked experts captained Haaland 46.9% of the time, against 23.2% for Bruno Fernandes, who had more hauls. Following the template captain is itself not always optimal. https://www.fantasyfootballscout.co.uk/2026/06/02/who-finished-1st-in-fpls-the-great-and-the-good

**Folklore** [F]
- "Differentials win you rank." That holds only when they outscore the owned alternatives, and on average more risk means lower expected reward. https://www.fantasyfootballscout.co.uk/2020/06/30/are-differentials-always-the-most-effective-route-to-fpl-success/
- Fixed rules such as "a captain under 10% EO is better" are unverified. One example is https://onsidearena.com/tips/fpl-captains-to-avoid-2026-27.

### 1.4 Team value and price-change chasing

- **[E]** A modelled optimal Squad gains about 20 points per £1m of team value over a full season, with diminishing returns. "Don't take hits for value." https://www.fantasyfootballscout.co.uk/2019/09/12/the-value-of-team-value/
- **[E]** Correlational finding: £1m more team value at Gameweek 19 was associated with about 21.8 more final points (R² = 0.169). The direction is confounded, because good Managers both gain value and score points. https://arxiv.org/abs/2009.01206
- **[E]** Solvers value cash in the bank at about 0.08 points per £1m (open source) or 0.10 (FPL Review). Sources as in 1.1.
- **[P]** Mark Sutherns finished 2025/26 with the highest team value of FFScout's tracked experts, £105.9m, "by making early transfers to capture price rises". Fabio Borges finished lowest at £100.9m and still finished well. https://www.fantasyfootballscout.co.uk/2026/06/02/who-finished-1st-in-fpls-the-great-and-the-good
- **[P]** Låbakk pays almost no attention to team value and transfers late, because team news is worth more to him than small price moves.
- **[E]** Elite Managers make most of their transfers late (Friday or Saturday before the deadline). About a quarter of the Footballers they sell are doubtful, injured or suspended. The 2025/26 Top 50 bought rising Footballers more often than average Managers but "still missed many price rises". https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/
- **[I]** The value of a £0.1m rise falls roughly in proportion to the Gameweeks left. By about Gameweek 30 it is close to zero. Price changes are mechanised in ticket 04.

### 1.5 Bench order and which positions to bench

- **[E]** Solver weights show how often each bench slot is actually needed:
  - FPL Review: Sub 1 0.30, Sub 2 0.10, Sub 3 0.03, backup goalkeeper 0.03.
  - Open source: Sub 1 0.21, Sub 2 0.06, Sub 3 0.002, backup goalkeeper 0.03.

  Spending on the bench beyond what keeps autosubs working is therefore nearly wasted outside Bench Boost Gameweeks. Sources as in 1.1.
- **[E]** Autosubs must keep a legal formation, so Sub 1 is skipped if he would break it. Fielding 3 defenders with 3 outfield bench players is the setup most exposed to failed autosubs. https://onefpl.com/blog/fpl-auto-subs-bench-order-rules (a secondary guide; the rule itself is FPL's)
- **[P]** Common elite structure: the cheapest playing goalkeeper on the bench, the cheapest nailed defenders, and one cheap midfielder or defender as Sub 1. Defensive contribution points, kept for 2026/27, give some cheap defenders and midfielders a near-4-point floor. That makes them better Sub 1 choices. https://www.fantasyfootballscout.co.uk/2026/10/01/should-fpl-managers-keep-rolling-the-dice
- **[I]** Order the outfield bench by P(needed) × xP | plays, where P(needed) is driven by starters' minutes risk. The Footballer most likely to come on should be the one with the best expected minutes, not the best fixture.

### 1.6 Overall rank versus mini-league: risk when behind or ahead

- **[E]** In the overall game, variance averages out across millions of Squads, so the best policy is close to maximising xP. In a mini-league, only a few Rivals matter. https://www.fantasyfootballscout.co.uk/2020/07/16/what-is-the-best-strategy-for-defending-a-fantasy-premier-league-mini-league-lead
- **[E]** Frontier Economics ran a Monte Carlo on historical FPL data, comparing pairs of Footballers with equal mean points. https://www.frontier-economics.com/uk/en/news-and-insights/articles/article-i7337-how-to-win-your-fantasy-football-league/
  - When chasing a 20-point deficit over 7 Gameweeks, 2 "maverick" (high-variance) differentials succeeded in 32% of simulations, against 22% for 2 safe picks.
  - The benefit diminishes beyond 2 for gaps of 10–30 points. They recommend 2–4 at most.
  - In-form Footballers with easy fixtures roughly double the base rate of 10-point hauls (base about 5%).
- **[E]** Daily-fantasy research makes the same structural point. Haugh & Singal (*Management Science*, 2021) modelled opponents' selections and treated the contest as beating a stochastic benchmark. In winner-takes-most contests this returned about 350%, against 50% for a portfolio that ignored opponents. https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.2019.3528 (the figure is from Imperial College's summary of the paper)
- **[E]** Hunter, Vielma & Zaman built entries for top-heavy payoffs that maximise mean subject to a minimum variance. https://arxiv.org/abs/1604.01455
- **[P]** Mini-league "shields and swords": own Rivals' high-EO Footballers to defend a position, and hold Footballers they lack to attack it. https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions
- **[P]** Defending a lead: template the captain and avoid unusual differentials. Shadowing gets harder as the number of close Rivals grows. Source as above (Simon March, 2020).
- **[P]** Simon March (2015 champion) argues that focusing on Rivals may even help overall rank, by filtering out ownership noise. He also says to time Chips around Rivals who are "dead-ending". This is untested. https://www.fantasyfootballscout.co.uk/2022/02/04/mini-leagues-v-effective-ownership-does-mini-beat-macro-in-fpl
- **[I]** For the Overall rank Goal, the right EO reference is the cohort near the Member's target rank, not all Managers. The relevant EO "treats you differently at different ranks" (https://allaboutfpl.com/2021/07/what-is-effective-ownership-in-fpl-fpl-guide/). A Member around 500k should weight top-100k EO. A Member chasing top 10k should weight top-10k EO.

### 1.7 Luck versus skill: what "consistently top" means

- **[E]** The season-to-season points correlation is 0.42 (2017/18 to 2018/19) and decays over longer gaps. Each season of experience adds about 22 points. https://arxiv.org/abs/2009.01206
- **[E]** FPL Review, 2021:
  - Managers with 4+ prior top-10k seasons had about a 30% chance of making top 10k again.
  - Three consecutive top-10k finishes are about as likely to come from a top-100k-skill Manager as from a top-100 one.
  - FPL Review recommends EV-based review instead of rank-based review.

  https://docs.fplreview.com/articles/top-10k/
- **[E]** FPL Review's Season Review measures luck as realised points against xP-based metrics. It also scores "Shared EV" against "Differential EV" relative to the Elite 1000's EO, and records Burnt FTs and Total Hits. https://docs.fplreview.com/team-analysis/season-review-glossary/
- **[P]** Ibsen attributes his win to "a mix of both", skill and luck. In FFScout's tracked expert group, 8 of the members finished inside the top 1% in 2025/26, and one finished 1,828th. Source as in 1.3.

---

## 2. Decision playbook (for the bot to encode)

All numbers are defaults that the code computes in Analyst mode. Values drawn from solver docs are marked; the rest are my proposals [I] to tune by backtest.

### 2.0 Shared core (both Goals)

1. **Objective.** Maximise Σ over Gameweeks g = 1…H of decay^(g-1) × (lineup xP + captain xP + 0.1 × vice-captain xP + bench_w · bench xP) + FT_roll_value + 0.08 × ITB(£m) − 4 × hits. Defaults: H = 6–8, decay = 0.85–0.9, and transfers are not planned in the last 2 horizon Gameweeks. [E]
2. **Free transfers.**
   - Roll only if no available move gains more than the roll value for the current FT state: 2.0, 1.6, 1.3, 1.1, and 0 at 5 FTs.
   - At 5 FTs, always use at least one.
   - Add a 0.2 use-penalty so that trivial moves are not recommended. [E]
3. **Hits.**
   - Default is no hits.
   - Recommend a -4 only if the decayed horizon xP gain of the extra move is at least 4 + the FT roll value forgone + a noise margin. A noise margin of about 1.5 xP is my proposal, reflecting FPL Review's "0.5 EV over 12 GWs is noise" warning plus model error. [I]
   - Typical cases that qualify: replacing a starter with xMins ≈ 0 when no valid autosub exists, or a hit made alongside ≥1 FT to fix a structural problem before a fixture swing. [P]
   - A recommendation must not depend on a single solve. Accept a move only if it appears in most randomised solves; open-source `randomized` gives 5 or more. [E][I]
4. **Captain.**
   - Pick the highest xP.
   - Vice-captain: the highest xP among starters with a different match and kickoff time. [I]
   - Treat captain options within about 0.3 xP of each other as tied. Ties are broken by the Goal-specific rule below. [I]
5. **Team value.**
   - Never recommend a transfer or a hit for value alone. [E]
   - Once a transfer is already decided, recommend making it before an imminent Price change only if no team-news risk remains for either Footballer, and only before about Gameweek 30. Otherwise wait for news. [P][I]
   - Price alerts follow ticket 15. Value enters the objective only through ITB (0.08/£m) and selling prices.
6. **Bench.**
   - Bench order: outfield subs sorted by P(needed) × xP | plays, using weights of about 0.2–0.3 for S1, 0.06–0.1 for S2 and about 0.01 for S3. [E]
   - Check that autosubs keep the formation legal, and warn if a likely-blank starter cannot be covered. [E]
   - Buy and structure advice: a cheap playing goalkeeper on the bench, and cheapest nailed defenders and defensive-contribution midfielders as fodder. Bench spend should be as low as possible except in the 1–2 Gameweeks before a planned Bench Boost. [P][I]
7. **Process scoring.** Score every past recommendation on xP at the deadline, not on realised points, and show luck separately. [E]

### 2.1 Overall rank Goal (the default)

- **Reference group.** Choose the Elite cohort near the Member's current or target rank: top 10k if the Member is inside about the top 50k, otherwise top 100k. Compute the Elite gap from that cohort's Elite ownership and EO. [I]
- **Risk.** Start at EO-risk λ = 0, keeping it within ±0.15 FPL-Review-style (score = xP − λ·EO·xP). The bot stays essentially an xP maximiser. [E]
- **Captain tie-break.** Among tied options, prefer the higher-EO one when the Member is near a rank target they want to protect. Prefer the lower-EO one when the Member is far below their target with fewer than about 10 Gameweeks left. [I]
- **Template core.** Flag every Footballer with Elite EO ≥ 100% that the Member lacks as a "shield" Gap, with its expected rank swing. Recommend buying him only if the move also passes the xP rule. [I]
- **Differentials.** Allow 1–3 deliberate differentials (Elite ownership < 10%) only when their horizon xP is at least the template alternative's. Never recommend one for variance alone. [P][I]

### 2.2 Mini-league Goal

- **Reference group.** The Member's Rivals in the chosen league. Compute Rival EO, meaning each Rival's ownership × captaincy weighted by how close that Rival is to the Member in the standings, and the Rival gap. [P][I]
- **State.** For each close Rival, compute lead L, Gameweeks left n, and an estimated per-Gameweek standard deviation σ of the points difference between the two Squads. The bot should estimate σ empirically from both Squads' history and the Rival gap; no source gives a number. Set z = L / (σ√n). [I]
- **Ahead** (z ≳ +1, a clear lead) [P][I]:
  - Shield. Match the Rivals' captain when the xP gap is within the tie band.
  - Prefer buying Rival-owned Footballers among xP-tied options.
  - Avoid hits that only add variance.
  - Late in the season, mirror Rivals' Chip timing where possible.
- **Close** (|z| < 1): use the Overall rank rules, but with Rival EO in place of Elite EO.
- **Behind** (z ≲ −1, a clear deficit) [E][I]:
  - Sword. Prefer Footballers the Rivals don't own among options within about 0.5 xP over the horizon.
  - Target 2 (and at most 4) high-variance differentials.
  - Consider a different captain from the leader's when xP is tied or close: accept up to about 10% less captain xP when n ≤ 6.
  - Time Chips away from the leader's so that they add variance.
  - Hits may be tolerated slightly more when n is small and |z| is large.
- **Hopeless** (z ≪ −2 with few Gameweeks left): tell the Member honestly that only maximum variance gives any chance, or suggest switching back to the Overall rank Goal. [I]
- Run all of these thresholds through a Monte Carlo of Member against Rivals, sampling Footballer points around xP, rather than as fixed cut-offs. [E][I]

---

## 3. Implications for the bot's design

- **Analyst mode needs a multi-Gameweek MILP**, not a one-Gameweek ranker. Reuse or port the formulation from Sertalp Bilal's Apache-2.0 `FPL-Optimization-Tools` (HiGHS via `highspy`). Its settings already cover FT states, bench weights, ITB, decay, hit limits and randomised solves. Ticket 07 should confirm the xP source.
- **Goal belongs in the objective, not in the prompt.** Overall rank uses Elite EO with λ ≈ 0. Mini-league uses Rival EO plus a win-probability simulation. Both reuse the same solver and only change the reference group and the risk term. Claude only explains the result.
- **Data needs:**
  - Elite ownership including captaincy, for top 10k and top 100k (ticket 03).
  - Each Rival's picks and captain every Gameweek, available from the public FPL entry endpoints (ticket 01).
  - Member FT state, bank, and selling prices.
- **Robustness layer:** run N randomised solves and recommend only consensus moves. Report "tie" when xP gaps fall below the noise band, so that Members are not pushed into churn.
- **Explanations should say which category a reason falls in**: evidence (xP), practice ("elite Managers usually…"), or a Goal-specific risk choice. That keeps folklore out of the numbers.
- **Feedback loop:** a weekly process score of xP decision quality plus a luck term, in the style of FPL Review's Season Review.

## 4. Open questions

1. When a Member plays a Wildcard or Free Hit in 2026/27, do they still gain the +1 FT for that Gameweek, or only keep the ones saved? The PL pages confirm saved FTs aren't reset but don't state accrual. Check this against the FPL API's `transfers` and history data (ticket 01/06).
2. No published study gives the empirical σ of the weekly points difference between two Squads by Rival-gap size. The bot will have to estimate it from data.
3. The solver hyperparameters (decay, FT values, bench weights) have never been publicly backtested. The bot should backtest them on 2025/26 data with its own xP.
4. No source quantifies the payoff of chasing Price changes when the timing risk of early transfers is taken into account. Ticket 04 may help.
5. How large should the EO tie band and λ be for Members far from the Elite cohort, for example 2M overall? My proposal is to start at 0 and tune.
6. The Fantasy Football Fix "Top 50" and "All-Time Top 50" selection methods are not published.

## 5. Sources

Primary (solver docs and code, rules):
- https://docs.fplreview.com/the-model/solvers/settings/
- https://docs.fplreview.com/the-model/solvers/into-to-solvers/
- https://docs.fplreview.com/the-model/solvers/solver-comparison/
- https://docs.fplreview.com/the-model/projections/expected-value/
- https://docs.fplreview.com/team-analysis/season-review-glossary/
- https://docs.fplreview.com/articles/top-10k/
- https://github.com/sertalpbilal/FPL-Optimization-Tools
- https://raw.githubusercontent.com/sertalpbilal/FPL-Optimization-Tools/main/data/README.md
- https://raw.githubusercontent.com/sertalpbilal/FPL-Optimization-Tools/main/data/comprehensive_settings.json
- https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627
- https://www.premierleague.com/en/news/4059225
- https://www.premierleague.com/en/news/4058895

Published analyses and papers:
- O'Brien, Gleeson & O'Sullivan, "Identification of skill in an online game: The case of Fantasy Premier League": https://arxiv.org/abs/2009.01206
- Haugh & Singal, "How to Play Fantasy Sports Strategically (and Win)", *Management Science* 2021: https://pubsonline.informs.org/doi/pdf/10.1287/mnsc.2019.3528
- Hunter, Vielma & Zaman, "Picking Winners in Daily Fantasy Sports Using Integer Programming": https://arxiv.org/abs/1604.01455
- Ramezani & Dinh, "A data-driven framework for team selection in FPL": https://arxiv.org/abs/2505.02170
- Frontier Economics, mini-league Monte Carlo: https://www.frontier-economics.com/uk/en/news-and-insights/articles/article-i7337-how-to-win-your-fantasy-football-league/
- FFScout, "The value of team value" (2019): https://www.fantasyfootballscout.co.uk/2019/09/12/the-value-of-team-value/
- FFScout, PGLT (FPL Theorist, 2021): https://www.fantasyfootballscout.co.uk/2021/10/08/points-gained-over-the-lifetime-of-a-transfer
- Fantasy Football Fix, Top 50 transfer behaviour 2025/26: https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/

Elite Manager practice (interviews and columns):
- Jonas Sand Låbakk (2023/24 champion): https://www.fantasyfootballscout.co.uk/2024/05/27/an-interview-with-fpl-2023-24-champion-jonas-sand-labakk/
- Lovro Budišin (2024/25 champion): https://fpl.page/article/an-interview-with-lovro-budisin-fpl-world-champion and https://www.premierleague.com/news/4322425
- Erik Ibsen (2025/26 champion): https://allaboutfpl.com/2026/03/interview-with-world-number-1-fpl-manager-erik-ibsen-2025-26/
- FFScout "The Great and The Good" 2025/26 review: https://www.fantasyfootballscout.co.uk/2026/06/02/who-finished-1st-in-fpls-the-great-and-the-good
- Zophar column archive: https://www.fantasyfootballscout.co.uk/category/pro-pundits-zophar/
- Seb Wassell on EO: https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions
- Simon March on mini-leagues: https://www.fantasyfootballscout.co.uk/2022/02/04/mini-leagues-v-effective-ownership-does-mini-beat-macro-in-fpl and https://www.fantasyfootballscout.co.uk/2020/07/16/what-is-the-best-strategy-for-defending-a-fantasy-premier-league-mini-league-lead
- Simon on differentials: https://www.fantasyfootballscout.co.uk/2020/06/30/are-differentials-always-the-most-effective-route-to-fpl-success/
- A. Yousef, 2026/27 column: https://www.fantasyfootballscout.co.uk/2026/10/01/should-fpl-managers-keep-rolling-the-dice

Secondary (used only for rule explanations):
- https://allaboutfpl.com/2021/07/what-is-effective-ownership-in-fpl-fpl-guide/
- https://onefpl.com/blog/fpl-auto-subs-bench-order-rules
- https://onsidearena.com/tips/fpl-captains-to-avoid-2026-27 (cited as an example of folklore)
