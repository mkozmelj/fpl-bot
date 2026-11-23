# 2026/27 Chip rules and how to time each Chip

Research for ticket `issues/06-chip-rules-and-strategy.md`. Written 2026-11-19.

FPL data comes from one snapshot of `bootstrap-static` and one of `fixtures`, both taken 2026-11-19 (`game_config.status.price_change_last_updated` = 2026-11-19T17:05Z). In that snapshot GW10 is the current, finished Gameweek, and the next deadline is **GW11 on Sat 21 Nov 2026 at 11:00 UTC**. So we are at the GW11 deadline, not GW12.

Labels used below: **[Fact]** means a primary source states it (the FPL API, premierleague.com, thefa.com, uefa.com). **[Reported]** means a reputable secondary source states it and I could not confirm it first-hand. **[Projection]** means a forecast.

---

## TL;DR

- **[Fact]** There are **8 Chips: two sets of Wildcard, Free Hit, Bench Boost and Triple Captain**. The first set is valid GW1–19 and the second set GW20–38. Nothing about Chips changed from 2025/26. Only **one Chip can be played per Gameweek**. Wildcard and Free Hit open in **GW2**. Bench Boost and Triple Captain could be played from GW1. [S1][S2][S3]
- **[Fact] The real first-half cut-off is the GW19 deadline: Fri 1 Jan 2027, 18:30 UTC.** The premierleague.com articles still say "13:30 GMT Sat 2 January", but a TV pick (Leeds v Everton, Fri 1 Jan 20:00) moved the deadline after those articles were written. The bot must read deadlines from `events[].deadline_time`, never from articles. [S1][S3]
- **[Fact]** A Free Hit in GW19 rules out a Free Hit in GW20. Wildcard and Free Hit **cannot be cancelled** once confirmed. Bench Boost and Triple Captain can be cancelled until the deadline. Banked free transfers are **kept** when a Wildcard or Free Hit is played. [S2][S4]
- **[Fact]** The fixture list has **no blank or double Gameweeks yet**. All 380 fixtures are scheduled, and every Gameweek from GW1 to GW38 has exactly 10 matches. [S3]
- **[Projection, high]** **BGW30** (EFL Cup final on 21 Mar 2027) and **BGW33** (FA Cup semi-finals on 24–25 Apr 2027). **[Projection, medium]** **DGW32, DGW35 and/or DGW36**, using the free midweeks of 20–22 Apr, 11–13 May and 18–20 May. **[Projection, low]** a disrupted GW37 around the FA Cup final (Sat 22 May) and the Europa League final (Wed 26 May). [S5][S6][S7][S8][S9]
- **[Fact]** The FA Cup R3, R4, R5 and quarter-final dates all fall on weekends with no Premier League round. That leaves only the semi-finals to cause a blank. [S7][S3]
- **First-half set (still live for many Members):** no doubles are expected before GW19. Elite managers therefore spent their first set on **strong single Gameweeks**. In 2025/26 that meant Haaland Triple Captains against weak home opponents, and a Free Hit to dodge a clash between two highly owned clubs. They played Bench Boost soon after a Wildcard. [S10][S11]
- **Second-half set:** the usual elite route is to save Free Hit for the biggest blank, pair Bench Boost with the biggest double (often after a Wildcard that builds the double-Gameweek Squad), and use Triple Captain on a double or on a premium forward's best home fixture. In 2025/26 the Top 50 converged on Bench Boost in DGW33 and Free Hit in BGW34. [S10]
- **Optimiser:** treat Chip timing as a joint mixed-integer problem over the remaining window. Use binary chip-per-Gameweek variables, one chip per Gameweek, one use per half, and an expiry at the GW19 and GW38 deadlines. The objective is Expected points (xP) with each Chip's effect included. Tune the horizon and decay on uncertain future fixtures. An open-source reference solver already models this with `chip_limits`, `allowed_chip_gws` and `forced_chip_gws`. [S12]

---

## 1. Chip rules (2026/27)

### 1.1 Inventory and windows

The table below is [Fact] from `bootstrap-static.chips` [S3].

| id | name (API) | chip_type | start_event | stop_event |
|---|---|---|---|---|
| 1 | `wildcard` | transfer | 2 | 19 |
| 3 | `freehit` | transfer | 2 | 19 |
| 4 | `bboost` | team | 1 | 19 |
| 5 | `3xc` | team | 1 | 19 |
| 2 | `wildcard` | transfer | 20 | 38 |
| 6 | `freehit` | transfer | 20 | 38 |
| 7 | `bboost` | team | 20 | 38 |
| 8 | `3xc` | team | 20 | 38 |

- [Fact] There are two sets of four and eight Chips in total. The first set "must be played before the Gameweek 19 deadline" and **cannot be carried over** into the second half. [S1][S2]
- [Fact] premierleague.com states the Chips are unchanged from 2025/26 ("Just like last season"). The Assistant Manager chip from 2024/25 is not part of the game: the API lists only these 8 Chips. [S1][S2][S3]
- [Fact] **Deadline discrepancy.** The articles give the GW19 deadline as 13:30 GMT on Sat 2 Jan [S1][S2]. The live API gives `2027-01-01T18:30:00Z` (Fri 1 Jan) because Leeds v Everton is now set for Fri 1 Jan at 20:00 UTC [S3]. FPL deadlines fall 90 minutes before the first kickoff of the Gameweek. **The API wins.**
- [Fact] All deadlines are in UTC (`game_settings.timezone = "UTC"`) [S3].

### 1.2 What each Chip does

- **Wildcard:** [Fact] all transfers in the Gameweek are free and permanent. It is played when the Manager confirms transfers that would otherwise cost points. It **cannot be cancelled** once activated. Banked free transfers are **kept**. [S4]
- **Free Hit:** [Fact] unlimited free transfers for one Gameweek. At the next deadline the Squad reverts to its pre-Free-Hit state. It cannot be cancelled once confirmed and cannot be played in GW1. If the first-half Free Hit is played in GW19, the second-half Free Hit cannot be played in GW20. [S1][S4] [Reported] Banked free transfers are kept. [S4] states this explicitly only for the Wildcard. OneFPL's 2026/27 rules hub says both chips keep them. [S13]
- **Bench Boost:** [Fact] the 4 bench Footballers' points count for that Gameweek. It is played on the Pick Team page and can be cancelled before the deadline. [S4]
- **Triple Captain:** [Fact] the captain scores ×3 instead of ×2. It can be cancelled before the deadline. [S4] [Reported, prior seasons] If the captain does not play, the vice-captain's points are tripled. The 2026/27 article does not say this [S4], so check it in the in-game help.
- **Combining:** [Fact] "Only one chip can be played in a single Gameweek." No pair of Chips can be stacked, including FH+BB, WC+BB and TC+BB. Back-to-back use is allowed: [S1] notes Bench Boost can be played the Gameweek straight after a Wildcard. [S1][S4]

### 1.3 Adjacent 2026/27 rules that affect Chip value

These are all [Fact].

- Up to 5 free transfers can be banked (`max_extra_free_transfers: 4` on top of the weekly 1) [S2][S3].
- **No extra December free transfers this season**, because there is no AFCON in 2026/27 [S2].
- Defensive contribution points continue (`defensive_contribution` is 2 points for DEF, MID and FWD) [S2][S3]. This keeps elite defenders viable as Triple Captain picks [S10].
- Scores now lock at 09:00 UK time the day after a Gameweek's last match [S2].
- Usage context [Fact, S3]: across GW1–10, first-half plays out of 11.3M Managers are Wildcard 4.00M (35%), Triple Captain 3.91M (35%), Bench Boost 2.45M (22%) and Free Hit 1.93M (17%). The single largest spike was 1.79M Triple Captains in GW3. Most Managers therefore still hold at least one first-half Chip with 9 Gameweeks (GW11–19) left.

---

## 2. Timing strategy per Chip

The guidance below comes from secondary analysis of elite behaviour, so read it as [Reported]. Elite evidence comes mainly from Fantasy Football Fix's study of 2025/26 Top 50 and All-Time Top 50 managers [S10], plus Hub and Scout chip guides [S11][S14].

### 2.1 First-half set (GW11–19 left)

The structural fact: **no blanks or doubles are expected before GW19** [S5][S6][S11]. Under the two-set system, elite managers stopped waiting for doubles and attacked strong single Gameweeks instead [S10].

- **Triple Captain:** the safest profile is a premium forward at home to a weak side. In 2025/26 the Top 50 played Haaland in GW6 (v Burnley) and GW17 (v West Ham) [S10]. FPL's own FDR in the current fixture list [S3] gives these 2026/27 GW11–19 candidates for Haaland, who is 78.8% owned and the most-captained Footballer:
  - GW11: FUL (H), FDR 2
  - GW16: HUL (H), FDR 2. Hub also names this week [S11].
  - GW19: TOT (H), FDR 3

  Hub's other named targets are Saka in GW19 (IPS, H) and Bruno Fernandes in GW14 (COV, H) [S11]. A defender Triple Captain under defensive contribution points (Gabriel) was popular but failed in 2025/26, showing that a defender's ceiling is less reliable [S10].
- **Free Hit:** the first-half Free Hit acts as a problem-solver. In 2025/26 the Top 50 played it in GW13 to target three teams' good fixtures and to avoid two highly owned clubs meeting each other [S10]. Hub's advice is to hold it in case a surprise winter double appears, and otherwise to use it when your Squad's xP is unusually low relative to the best available Squad [S11].
- **Wildcard:** play it in an international break, when there is time and data to rebuild. The GW11 break (now) is Scout's suggested window, and GW13 and GW17 are named as fixture-swing re-entry points [S14]. Note the festive run: GW17 (26–27 Dec), GW18 (29–30 Dec), GW19 (1–3 Jan) and GW20 (5–7 Jan) are four deadlines in about 10 days [S3]. Squad depth matters more then.
- **Bench Boost:** first-half Bench Boost plays by the Top 50 were **spread out, with no common week** [S10]. The consensus is to play it soon after a Wildcard, while all 15 Footballers are fit, nailed starters with good fixtures [S11]. Avoid congested festive Gameweeks if rotation risk is high. This is a judgement, so the bot should model minutes per Footballer rather than apply a rule.

### 2.2 Second-half set (GW20–38)

- **Free Hit:** keep it for the **largest blank**. In 2025/26 the clear peak for both elite groups was BGW34, the blank right after DGW33 [S10]. For 2026/27 that points to **BGW33** (FA Cup semi-finals), which can blank up to 8 teams [Projection].
- **Bench Boost:** play it in the **largest double**, after a Wildcard that builds a 15-man double-Gameweek Squad. In 2025/26 the Top 50 played it in DGW33, with some use in GW35–38 [S10]. For 2026/27 the candidates are DGW32, DGW35 and DGW36 [Projection].
- **Triple Captain:** a double-Gameweek premium (2025/26 split between Haaland and Gabriel) or, if the doubles are small, the best single home fixture of a premium forward [S10]. One cautionary case: Haaland's DGW36 Triple Captain in 2025/26 lost value because he did not appear in the second match [S10]. Model minutes in each leg of a double separately.
- **Wildcard:** most often used to set up the Bench Boost double, or the Free Hit blank followed by the Bench Boost double. Its timing is driven by when the rearranged fixtures are confirmed [S10].
- **Pairings:**
  - **WC → BB:** the Wildcard builds a Squad of 15 starters for the double, and the Bench Boost plays the week after.
  - **FH (blank) + BB (adjacent double):** this needs the base Squad to be built for the double, while the Free Hit covers the blank.
  - A Chip can never be stacked on another in the same Gameweek [S1][S4].
- **Herding caveat:** fewer and smaller doubles and blanks pushed most top managers onto the same Chip routes in 2025/26 [S10]. For a Member whose Goal is **Mini-league**, the Rival gap on Chips matters more than the Elite gap: playing the same Chip in the same Gameweek as a Rival only cancels out.

---

## 3. Known and projected blank and double Gameweeks, 2026/27

### 3.1 Calendar facts

- FPL Gameweek deadlines [S3]:
  - GW29: 13 Mar
  - GW30: 20 Mar
  - GW31: 10 Apr, after the March international break and the FA Cup quarter-final weekend
  - GW32: 17 Apr
  - GW33: 24 Apr
  - GW34: 1 May
  - GW35: 8 May
  - GW36: 15 May
  - GW37: **Sun 23 May**
  - GW38: 30 May
- **Every fixture from GW24 onward is still on a placeholder kickoff** (Sat 15:00 or 14:00 UTC), so TV picks have not yet been made for those Gameweeks [S3].
- FA Cup dates [S7]:
  - R3: Sat 9 Jan
  - R4: Sat 13 Feb
  - R5: Sat 6 Mar
  - Quarter-finals: Sat 3 Apr
  - **Semi-finals: Sat 24 Apr**
  - Final: Sat 22 May

  Cross-checking with the API: R3, R4, R5 and the quarter-finals all fall on free Premier League weekends (between GW20 and GW21, GW25 and GW26, GW28 and GW29, and GW30 and GW31). **Only the semi-finals collide with a Premier League round (GW33).** [S3][S7]
- EFL Cup [Reported]:
  - Quarter-finals: w/c 14 Dec, a free midweek between GW15 and GW16
  - Semi-finals: w/c 11 Jan and w/c 1 Feb
  - **Final: Sun 21 Mar 2027** [S8]. One Scout article says Sat 20 Mar [S5]. Either date is the GW30 weekend.

  The quarter-final ties are [Reported, S15]: Fleetwood v Everton, Man City v Bradford, Crystal Palace v Sunderland, and Liverpool v Bournemouth.
- Europa League [Fact, S9]:
  - Round of 16: 11 and 18 Mar
  - Quarter-finals: 8 and 15 Apr
  - Semi-finals: 29 Apr and 6 May
  - **Final: Wed 26 May 2027**

  English entrants: Bournemouth, Crystal Palace and Sunderland. [Reported] The Champions League final is 5 Jun 2027 and the Conference League final is 2 Jun 2027, both after GW38 [S16].

### 3.2 Calendar

| GW | Type | Status | Confidence | Mechanism / teams |
|---|---|---|---|---|
| 1–29, 31, 34 | normal | [Fact] 10 matches each, no blanks or doubles [S3] | high (barring weather or postponements) | — |
| **30** | **Blank** | [Projection] [S5][S6] | **high** | EFL Cup finalists' league games are postponed. If both finalists are Premier League clubs and not drawn against each other in GW30, 2 matches and **4 teams** blank. The candidate clubs and their GW30 ties [S3]: SUN (v ARS), BOU (@ BRE), LIV (@ FUL), CRY (@ IPS), MCI (v MUN) and EVE (v TOT). A finalist from the EFL (Fleetwood or Bradford) shrinks the blank. |
| **32** | **Double** | [Projection] [S6] | medium | The free midweek of 20–22 Apr [S5] falls inside GW32 (17–24 Apr). It is a natural slot for the GW30 games. The Europa League midweek is free (between the 15 Apr quarter-final and the 29 Apr semi-final) [S9]. |
| **33** | **Blank** | [Projection] [S5][S6] | **high** | FA Cup semi-finals on Sat 24 to Sun 25 Apr clash with GW33. The same pattern applied in the last two seasons [S6], and in 2025/26 [S17]: semi-finalists and their opponents blank. Up to 4 matches and **8 teams**, fewer if semi-finalists play each other in GW33 or are not Premier League clubs. The teams are known after the quarter-finals on 3 Apr. |
| **35 and/or 36** | **Double** | [Projection] [S5][S6] | medium | Free midweeks on 11–13 May (in GW35) and 18–20 May (in GW36) [S5] can absorb the GW33 games. |
| 37 | possible disruption | [Projection] [S5] | low | The FA Cup final on Sat 22 May falls the day before GW37's Sunday 23 May round. Scout sees a blank only if an FA Cup finalist also reaches the Europa League final on 26 May, which it calls "less-than-likely". |
| any | ad-hoc | — | — | Weather, safety or other postponements can create blanks or doubles at any time. Postponed games then need a free midweek. |

**What is not yet knowable:** which teams blank or double. The bot should refresh this from the API (see section 4.2) rather than hard-code it.

---

## 4. How a Chip planner could optimise

### 4.1 Predicting blanks and doubles early

Listed from earliest to latest signal.

1. **Calendar overlay (known in June).** Compare FPL `events` deadlines and fixture dates against the FA, EFL and UEFA round dates. A cup round on a Premier League weekend means a candidate blank. A free Premier League midweek means a candidate double slot. This is exactly how the BGW30, BGW33 and DGW32/35/36 projections above were made [S5][S6][S7][S9].
2. **Cup draws and results.** Each round narrows the set of affected clubs:
   - EFL Cup quarter-finals (w/c 14 Dec), then semi-finals (Jan/Feb), then the finalists for BGW30
   - FA Cup R3 (9 Jan) through the quarter-finals (3 Apr), then the semi-finalists for BGW33

   Probability of a blank for team *t* = P(*t* reaches the stage) × P(the stage clashes). Bookmaker or Elo cup-progress odds can supply the first term.
3. **Premier League rescheduling announcements.** The league confirms moved fixtures only once ties settle. In 2025/26 only 4 of 10 GW34 fixtures were confirmed before the FA Cup quarter-finals [S17]. In the API this shows up as fixtures with `event: null` (unscheduled) and then as per-team fixture counts other than 1 in a Gameweek [S3].
4. **TV picks.** These move kickoffs and therefore **deadlines**, as GW19 shows [S3]. They do not create blanks or doubles by themselves, but they decide whether a deadline falls on a Friday, which matters for Chip expiry and price-change timing.
5. **European progress.** Thursday Europa League ties push those clubs' league games to Sunday or Monday, which matters for rotation and minutes. They only cause a blank when a final collides with a round [S5][S9].

### 4.2 Data model hooks (FPL API)

- Chip windows: `bootstrap-static.chips[]` (`name`, `start_event`, `stop_event`). Do not hard-code GW19.
- Deadlines: `events[].deadline_time`.
- Blanks and doubles: count fixtures per (team, event) from `/api/fixtures/`. A count of 0 is a blank and a count of 2 or more is a double. `event: null` means postponed or not yet rescheduled.
- A Member's remaining Chips: their `entry/{id}/history` `chips` list compared against the windows.
- FDR for fixture swings: `team_h_difficulty` and `team_a_difficulty` in `fixtures`. A current GW11–19 FDR swing table can be built from this. On average FDR for GW15–19, Brentford, Arsenal, Liverpool and Sunderland have the easiest runs, and Ipswich, Tottenham, Hull and Coventry the hardest [S3].

### 4.3 Optimisation formulation

The chip effects below are fixed by the rules [S1][S4]. The solver design is my proposal.

Decision variables: binary `u[c,g]` for each Chip c ∈ {WC1, FH1, BB1, TC1, WC2, FH2, BB2, TC2} and each Gameweek g still inside c's window.

Constraints:

- Σ_g `u[c,g]` ≤ 1 for each Chip c. Use `= 1` when the window ends inside the horizon, because unused Chips are simply lost, so there is no reason to hold them past expiry.
- Σ_c `u[c,g]` ≤ 1 for each Gameweek g (one Chip per Gameweek).
- `u[FH1,19] + u[FH2,20] ≤ 1`.
- Wildcard and Free Hit are only allowed from GW2.

Chip effect on the objective, Σ_g xP(g), where `Δ` is the gain for that Gameweek:

| Chip | Gain in Gameweek g |
|---|---|
| TC | `Δ = xP(captain, g)`: one extra multiple of the captain's points. Credit the vice-captain fallback through P(captain plays). |
| BB | `Δ = Σ xP(bench_i, g)` for the 4 bench Footballers. Bench Footballers already carry a small auto-sub weight in a normal Gameweek, so the gain is the full bench xP minus that expected auto-sub value. |
| FH | `Δ = xP(best unconstrained 15, g) − xP(current Squad, g)`, with no carry-over to g+1. |
| WC | No single-Gameweek gain. It removes hit costs and free-transfer limits from the transfer path, so it **must** be solved inside a multi-period squad model rather than scored in isolation. |

Model choice: solve WC, FH, BB and TC **jointly** with the transfer plan, as a multi-period MIP over horizon H. BB value depends on how strong the bench is, and that depends on the transfers. TC value depends on who is owned, which depends on the WC. Ranking chips independently by single-Gameweek EV gain gives wrong answers whenever chips interact (WC → BB, FH + BB).

- **Reference implementation:** the Apache-2.0 open-source *FPL-Optimization-Tools* solver already exposes `use_wc`, `use_bb`, `use_fh`, `use_tc` (forced weeks), `chip_limits`, `allowed_chip_gws`, `forced_chip_gws`, `no_chip_gws`, `horizon` (default 8), `decay_base` (0.9), `bench_weights` and `ft_value` [S12]. A practical pattern is to solve the same problem under several candidate chip-week assignments and compare the objectives (scenario enumeration). This keeps the explanation simple for Analyst mode.
- **Uncertainty:** blanks and doubles past ~GW29 are probabilistic. Let the solver optimise against expected fixture counts, then treat "keep FH2 for BGW33 / BB2 for the biggest DGW" as an option whose value should only be given up when a single-Gameweek gain clearly beats the expected gain at the blank or double. Decay future xP (for example 0.9 per Gameweek).
- **Goal-aware tweak:** for Mini-league Members, weight the chip gain by how much it differs from Rivals' remaining Chips (Rival gap). For Overall rank, compare against the Elite cohort's likely Chip weeks (Elite gap).

---

## 5. Open questions

1. **Elite-cohort chip timing for 2026/27 is not published in aggregate.** `bootstrap-static` only gives totals across all Managers. Measuring it needs a sample of top-10k/100k entries' `entry/{id}/history`. That is a separate data ticket, and rate limits need care.
2. Triple Captain with a non-playing captain: confirm in the 2026/27 in-game help whether the vice-captain gets ×3. It did in earlier seasons, but this is not restated in [S4].
3. Banked free transfers on Free Hit: officially stated for the Wildcard only [S4]. Secondary sources say the Free Hit also keeps them [S13]. Verify in the in-game help.
4. EFL Cup final date: Sun 21 Mar per most sources [S8], Sat 20 Mar per [S5]. It does not change BGW30, but confirm on efl.com.
5. Champions League knockout dates were not verified from uefa.com. This only matters for whether 20–22 Apr is clear for every club.
6. GW37 and FA Cup final interplay: will finalists' GW37 matches (Sun 23 May) move? Watch for the Premier League's announcement.
7. Whether the premierleague.com chip articles will be corrected to the Friday GW19 deadline. That does not matter for the bot as long as it reads the API.

---

## Sources

- [S1] Premier League, "What's happening with FPL chips in 2026/27", 20 Jul 2026. https://www.premierleague.com/en/news/4679879/whats-happening-with-fpl-chips-in-202627
- [S2] Premier League, "All you need to know about changes to FPL for 2026/27", 31 Jul 2026. https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627
- [S3] FPL API snapshots, 2026-11-19: https://fantasy.premierleague.com/api/bootstrap-static/ (`chips`, `events`, `game_config`, `teams`, `elements`) and https://fantasy.premierleague.com/api/fixtures/ (per-team fixture counts, kickoffs, FDR).
- [S4] Premier League (The Scout), "How and when to use your chips in FPL", page dated 8 Nov 2026. https://www.premierleague.com/en/news/4362085/how-and-when-to-use-your-chips-in-202526-fantasy
- [S5] Fantasy Football Scout (FPL Marc), "When are the FPL blank and double Gameweeks in 2026/27?", 9 Nov 2026. https://www.fantasyfootballscout.co.uk/2026/11/09/when-are-the-fpl-blank-and-double-gameweeks-in-2026-27
- [S6] Fantasy Football Hub (Oli Poole, projections by Ben Crellin), "FPL Blank and Double Gameweek Guide 2026/27", 19 Jun 2026. https://www.fantasyfootballhub.co.uk/articles/fpl-blank-double-gameweek-guide
- [S7] The FA, "Emirates FA Cup round dates 2026-27". https://www.thefa.com/competitions/thefacup/round-dates
- [S8] Flashscore, "Everything you need to know about the EFL Cup draws, key dates and more" (2026/27; final Sun 21 Mar 2027). https://www.flashscore.co.uk/news/everything-you-need-to-know-about-the-efl-cup-draws-key-dates-and-more/xbmKdgdJ/
- [S9] UEFA, "2026/27 Europa League: teams, dates, draws, format, final". https://uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000--2026-27-europa-league-teams-dates-draws-format-final/
- [S10] Fantasy Football Fix, "2025/26 Chip Strategy: How the Best FPL Managers Used Double Chips", 22 Jul 2026. https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-chips-25-26/
- [S11] Fantasy Football Hub (Oli Poole), "FPL Chip Strategy Guide 2026/27: When to play the first set of chips", 3 Aug 2026. https://www.fantasyfootballhub.co.uk/articles/fpl-chip-strategy-guide
- [S12] sertalpbilal/FPL-Optimization-Tools (Apache-2.0), README and `data/comprehensive_settings.json`. https://github.com/sertalpbilal/FPL-Optimization-Tools
- [S13] OneFPL, "Quick FPL rules hub (2026/27)". https://onefpl.com/blog/fpl-rules-faq-2026-27
- [S14] Fantasy Football Scout, "The ultimate FPL chip strategy guide (updated)", 23 Oct 2026. Only the Wildcard section is public. https://www.fantasyfootballscout.co.uk/2026/10/23/the-ultimate-fpl-chip-strategy-guide-updated
- [S15] Sports Illustrated, "2026–27 Carabao Cup quarterfinal draw: all fixtures", 28 Oct 2026. https://www.si.com/soccer/2026-27-carabao-cup-quarterfinal-draw-all-fixtures
- [S16] 2027 UEFA Champions League and Conference League final dates as reported by Calcio e Finanza, 2 Sep 2025. https://www.calcioefinanza.it/2025/09/02/date-champions-league-2026-2027/
- [S17] Premier League, "How cup ties will cause Blank and Double Gameweeks in 2025/26 FPL", 9 Mar 2026. This covers the 2025/26 mechanism and precedent. https://www.premierleague.com/en/news/4536133
