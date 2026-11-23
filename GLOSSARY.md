# FPL Bot

An advisory assistant for a small invited group of Fantasy Premier League managers: it watches prices, predicts points, and recommends transfers, captaincy, bench order and chip timing.

## People and teams

**Member**:
One of the invited people using the bot, identified by their FPL team ID.
_Avoid_: User (ambiguous with FPL user), account, player

**Manager**:
Anyone who runs an FPL team, Member or not. A Member is a Manager; a Rival or Elite manager usually isn't.
_Avoid_: Owner, coach

**Squad**:
A Manager's 15 footballers for a Gameweek: 11 starters, 4 on the bench, with a captain and vice-captain.
_Avoid_: Team (ambiguous with Premier League club), lineup

**Footballer**:
A real Premier League player as listed in FPL, with a position, a club and a price.
_Avoid_: Player (ambiguous with a person playing FPL), asset

**Mini-league**:
A private classic or head-to-head FPL league that a Member belongs to.
_Avoid_: Private league, group

**Followed league**:
A Mini-league the bot tracks for a Member: their Goal's league, plus their small Mini-leagues.
_Avoid_: Watched league (clashes with Watch list)

**Rival**:
A Manager a Member competes with directly: a Manager in one of the Member's Followed leagues, or their head-to-head opponent this Gameweek.
_Avoid_: Opponent, friend

**Elite cohort**:
The managers ranked in the overall top 10k, or the top 100k, at a given Gameweek. These are two separate cohorts.
_Avoid_: Top players, pros, template

## Comparisons

**Elite ownership**:
The share of an Elite cohort that owns a Footballer, along with how often they captain him.
_Avoid_: Template, EO (unless the effective-ownership calculation is meant specifically)

**Gap**:
The Footballers, captain picks or chips where a Member's Squad differs from a reference group, weighted by how much that difference could swing points. It is an **Elite gap** when the reference is an Elite cohort, and a **Rival gap** when it is the Member's Rivals.
_Avoid_: Difference, delta

## Prices

**Price change**:
FPL's overnight rise or fall of a Footballer's price, driven by net transfers.
_Avoid_: Price move

**Price alert**:
The nightly message telling a Member which of their own Footballers may fall in price and which Watch-list Footballers may rise.
_Avoid_: Notification (too generic), price report

**Watch list**:
The Footballers a Member doesn't own but is thinking of buying, kept so the bot can alert them about price rises.
_Avoid_: Shortlist, targets

## Advice

**Gameweek**:
One FPL scoring round, which ends at the transfer deadline for the next one.
_Avoid_: Round, matchday

**Expected points (xP)**:
The bot's prediction of the FPL points a Footballer will score in a given Gameweek.
_Avoid_: Projection, forecast points

**Chip**:
A once-per-period FPL power-up, such as Wildcard, Free Hit, Bench Boost or Triple Captain.
_Avoid_: Booster, power-up

**Goal**:
What a Member's advice is tuned for: **Overall rank** (the default) or **Mini-league** (staying ahead of the Rivals in one chosen league). A Member can switch at any point in the season.
_Avoid_: Strategy, objective

**Analyst mode**:
The default way advice is produced: plain code computes every number and decision, and Claude only writes the explanation when a Member asks for one.
_Avoid_: Basic mode, math mode

**Scout overrides**:
The adjustments to a Footballer's expected minutes, and so to Expected points, that come from collected team news. They apply to every Member's advice, and a Member's own pasted note can add overrides to that Member's advice only.
_Avoid_: Scout mode, AI mode, news mode

**Advice mode**:
How the bot works for real Members: it only recommends, and the Member makes every change in FPL themselves.
_Avoid_: Manual mode

**Autopilot**:
A paper simulation in which the bot manages several Ghost Squads, each following a different Tactic, under real FPL rules, with no FPL account involved.
_Avoid_: Auto mode, bot mode, Sandbox account

**Ghost Squad**:
A simulated Squad that Autopilot runs under one Tactic. Its decisions lock at each deadline and it is scored from public data, so it can be compared with Members, Rivals and the other Ghost Squads.
_Avoid_: Bot team, test team

**Tactic**:
The fixed way of playing a Ghost Squad follows, such as maximising Expected points, following the Elite template, or backing differentials. It is set when the Ghost Squad starts and never changes.
_Avoid_: Strategy (clashes with Goal), variant
