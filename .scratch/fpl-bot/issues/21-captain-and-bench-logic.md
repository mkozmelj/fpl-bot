# Captain and bench logic

Type: grilling
Status: resolved
Assignee: owner
Blocked by: —

## Question

Given the xP model in [Expected-points model design](20-xp-model-design.md), how do xP, effective ownership and the Member's Goal become a captain, vice-captain and bench order? Decide the tie-break rule with EO, how the Goal (Overall rank or Mini-league) shifts risk, vice-captain and bench ordering under minutes uncertainty, and how this is worded in Telegram.

## Answer

Confirmed by the owner, 2026-11-20. All numbers are defaults that live in settings and are tuned by backtest.

- **Inputs and timing:** `/captain` and `/bench` run on demand against the last-deadline Squad, and the message says so (picks for the coming Gameweek are hidden, as in [Elite gap, Rival gap and the mini-league progress view](19-gap-views.md)). No push messages; the Price alert stays the only unsolicited message. The logic is a pure function over the xP and xMins table from [Expected-points model design](20-xp-model-design.md).
- **Captain:** the highest next-Gameweek xP (double Gameweeks summed, blanks 0). Options within **0.3 xP** of the top are tied. The top 3 are shown with xP.
- **Tie-break, Overall rank Goal:** the higher Elite captain share wins, from the 10k or 100k cohort chosen by the Member's rank. If the figure is missing or stale, the higher xP wins and the message says so. There is no EO risk term (λ = 0) and no "rank target" concept, since the Goal has none.
- **Vice-captain:** the best-xP starter whose club plays a different match from the captain, with start probability of about **85%** or more. If the captain is a double-Gameweek Footballer, the next best is used.
- **Starting XI and bench:**
  - The XI is the legal-formation maximum of xP (xMins is already inside xP).
  - The backup goalkeeper is always Sub GK.
  - Outfield subs are ordered by P(needed) × xP-if-plays. P(needed) is computed in plain code from start probabilities and formation legality, with no simulation.
  - The bot warns when a likely-blank starter cannot be covered by a legal autosub.
- **Mini-league Goal changes the captain only.** XI, vice-captain and bench stay xP-driven.
  - **State:** z = L / (σ√n) against the nearest Rival above and below. σ is the empirical standard deviation of the weekly points difference to that Rival from public history, shrunk toward a prior of about **15** points when fewer than 8 Gameweeks exist. Ahead is z ≥ +1, Behind is z ≤ −1, Close otherwise (Overall rank rules, with Rival captain share in place of Elite).
  - **Ahead:** within the tie band, match the Rivals' most common captain.
  - **Behind (n ≤ 6 Gameweeks left):** if a captain the leading Rival does not have is within **10%** of the top xP, recommend it and label it a variance choice. Otherwise keep the top-xP pick.
  - **Hopeless (z ≤ −2, n ≤ 4):** say so honestly and suggest switching the Goal back to Overall rank.
- **Wording:** a fixed template with no Claude call. A header with the Gameweek and "based on your GWn Squad", the top 3 captains with xP, then the vice-captain and the bench order with P(needed). Each reason carries a tag: Evidence (xP), Practice (Elite or Rival share) or Goal risk. Ties read "too close to call" and name the tie-break used. A differential is labelled a variance choice and never as "better". [Analyst-mode summaries and the fate of Scout mode](22-analyst-and-scout-modes.md) may wrap Claude prose around this later.
- **Chips are out of scope here.** The logic assumes no Chip. The chip planner may call it with a chip-active flag (Triple Captain applies the captain rule at 3×, Bench Boost orders the bench as starters).
- **Checking it:** an owner-only xP-versus-realised comparison per Gameweek (the bot's pick against the top-xP pick, FPL's most-captained Footballer and `ep_next`'s pick). The Core versus Baseline Ghost Squads ([Autopilot paper simulation: rules and how it's shown](17-autopilot-paper-simulation.md)) are the end-to-end check. No per-Member tracking of what Members captained.
- **Backtest follow-ups (settings, not new tickets):** the 0.3 tie band, the 85% start-probability floor, the σ prior of 15 and the 10% differential allowance are tuned in the same backtest as [Expected-points model design](20-xp-model-design.md).
