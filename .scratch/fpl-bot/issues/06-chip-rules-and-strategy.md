# 2026/27 chip rules and how to time each chip

Type: research
Status: resolved
Blocked by: —

## Question

Which Chips exist in FPL 2026/27, and what are their exact rules? Cover how many there are, whether there is one set per half of the season, deadlines (for example "use before the GW19 deadline"), and whether chips can be combined.

How do top managers pick the Gameweek for each chip? Consider:
- double and blank Gameweeks
- the fixture-swing calendar
- cup-round knock-on effects
- Bench Boost pairing with a Wildcard or Free Hit
- Triple Captain targets
- the chip used to navigate a blank Gameweek

What data predicts double and blank Gameweeks early (cup draws, TV picks, rearranged fixtures)? Also cover how a chip planner could choose Gameweeks with an optimiser (expected-value gain per chip per Gameweek).

Findings go in `.scratch/fpl-bot/research/06-chip-rules-and-strategy.md`.

## Answer

- There are 8 Chips: two sets of Wildcard, Free Hit, Bench Boost and Triple Captain. The first set is valid GW1–19 (Wildcard and Free Hit from GW2) and the second set GW20–38. Only one Chip can be played per Gameweek. Wildcard and Free Hit cannot be cancelled. A GW19 Free Hit blocks a GW20 Free Hit. Nothing changed from 2025/26.
- The real first-half cut-off is the GW19 deadline on Fri 1 Jan 2027 at 18:30 UTC (from the API). The articles say Sat 2 Jan 13:30, but a TV pick has since moved it. The bot must read Chip windows and deadlines from `bootstrap-static` (`chips`, `events`) and never hard-code them.
- No blank or double Gameweeks exist yet: all 380 fixtures are scheduled, 10 per Gameweek. The projections are:
  - BGW30 (EFL Cup final), high confidence
  - BGW33 (FA Cup semi-finals), high confidence
  - DGW32 and DGW35/36 in free midweeks, medium confidence
  - a disrupted GW37, low confidence
- First half: no doubles are coming, so elite managers spend Chips on strong single Gameweeks. Examples are a Haaland Triple Captain at home to a weak side (GW11 Fulham or GW16 Hull this season), a Free Hit to dodge a clash between highly owned clubs, and a Bench Boost soon after a Wildcard.
- Second half: the elite pattern is Free Hit on the biggest blank (likely BGW33), Bench Boost on the biggest double after a Wildcard, and Triple Captain on a double-Gameweek premium.
- Early signals for blanks and doubles are, in order: cup dates against the Premier League calendar, then cup draws and results, then the Premier League's rescheduling notices (`event: null` fixtures), then TV picks (which move deadlines).
- The planner should solve the Chips jointly with transfers as a multi-period MIP: binary chip-per-Gameweek variables, one Chip per Gameweek, use-or-lose expiry and an xP objective with each Chip's effect. FPL-Optimization-Tools is an existing reference design.

Findings: [../research/06-chip-rules-and-strategy.md](../research/06-chip-rules-and-strategy.md)
