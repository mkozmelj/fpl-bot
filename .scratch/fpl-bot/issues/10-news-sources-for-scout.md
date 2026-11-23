# Legal free team-news sources for Scout mode

Type: research
Status: resolved
Blocked by: —

## Question

Which free, legally usable sources of Premier League team news (injuries, suspensions, press-conference quotes, predicted line-ups) can scripts collect before each deadline?

Consider:
- the FPL `news` field
- the official Premier League injury and press-conference pages
- club sites and RSS
- BBC Sport RSS
- the Reddit API (current free-tier terms)
- predicted-line-up sites
- the ToS of each

How should the material be cut down before Claude sees it, so tokens stay minimal? Options include keeping only Footballers owned by Members, on Watch lists, or with high Elite ownership; deduplicating; extracting quotes; and keyword filters.

Findings go in `.scratch/fpl-bot/research/10-news-sources-for-scout.md`.

## Answer

- The only source that is free, legal and automatable is the **FPL API** (`bootstrap-static`). For every Footballer it carries `status`, `news`, `chance_of_playing_*`, `scout_risks` (suspension risk, loan ineligibility) and `scout_news_link` (the club's own team-news article).
- The other sources all forbid automated collection, AI processing, or both: BBC Sport RSS, the Guardian API, the Premier League's injury page, club sites (e.g. Spurs), Fantasy Football Scout, Fantasy Football Hub, Sportsgambler and Reddit. Since Nov 2025, Reddit also needs approval for new API apps. Leave them out of v1.
- The FPL `news` text is templated (`N% chance of playing`, `Unknown return date`, `Expected back <date>`, `Suspended until <date>`, transfer or loan notes), so plain code can parse nearly all of it.
- v1 inputs: FPL news fields, parsed by code; optional Member-pasted notes, capped in length; and the `scout_news_link` shown to Members as a link, never fetched.
- Pre-filter: snapshot → pool (Squads, Watch lists, high Elite ownership, Gap Footballers) → diff since Claude's last read → regex parse → only unparsed records and keyword-filtered Member notes go to Claude. Estimated cost is about 1.5k–3k tokens per Gameweek, or 0 when nothing is left over.
- Open: whether Scout mode needs Claude at all on FPL-only data, and the FPL terms' claim of IP in "Game data", which affects the whole bot.
- Findings: [../research/10-news-sources-for-scout.md](../research/10-news-sources-for-scout.md)
