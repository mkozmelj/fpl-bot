# Legal free team-news sources for Scout mode

Research for ticket `issues/10-news-sources-for-scout.md`. Checked on 2026-11-19, the week of the Gameweek 11 deadline (2026-11-21 11:00 UTC). Terms of use change often, so re-check them before shipping.

Notation: **[F]** means a fact, read directly from the cited source. **[I]** means my inference or recommendation. Claims are cited by number; the list is at the end.

## TL;DR

- **[F]** The FPL API already carries structured team news for every Footballer: `status`, `news`, `news_added`, `chance_of_playing_this_round` and `chance_of_playing_next_round`. It now also has two newer fields. `scout_risks` covers suspension risk and loan ineligibility for a given Gameweek, and `scout_news_link` links to the club's own team-news article. No login is needed. [1]
- **[F]** The FPL `news` text is almost fully templated. Today's 197 entries were all one of a few patterns: `<injury> - N% chance of playing`, `- Unknown return date`, `- Expected back <date>`, `Suspended until <date>`, and transfer or loan notes. [1]
  - **[I]** Plain code can parse all of it. Claude adds almost nothing on FPL data alone.
- **[F]** Every unstructured source checked forbids automated collection, AI use, or both. That covers BBC Sport, the Guardian Open Platform, Fantasy Football Scout, Fantasy Football Hub, Sportsgambler, Tottenham's club site and Reddit. [3][4][6][7][8][9][10][11][12][13]
  - The BBC's robots.txt explicitly bans RAG, agentic AI and "summaries for your own use".
  - The Guardian's free API terms ban use "with any … artificial intelligence technologies".
- **[F]** Reddit has blocked all crawlers in robots.txt. Since November 2025, new Data API access needs Reddit's approval. Self-service app creation has closed. [10][11][12]
- **[F]** The Premier League's injury page is rendered in the browser from an undocumented API. Its site terms forbid "creating a database" from downloaded material and any commercial use. [2][5]
- **[I]** For v1, the only source that is both legal and automatable is **the FPL API itself**. Scout mode should parse it with plain code. Claude should see only the records that changed since its last read, plus optional **notes a Member pastes in themselves**.
- **[I]** That design costs roughly **1.5k–3k tokens per Gameweek**, including instructions and output. The changed-records payload itself is about 250–600 tokens.
  - For comparison: all news in compact form is about 3k tokens. All news-bearing records as raw JSON are about 11k tokens. Raw `bootstrap-static` is about 450k tokens.
- **[I]** The leftover legal risk is the same one the whole bot already carries. The FPL terms reserve "Game data" to the Premier League. Scout mode adds no new risk as long as it stays on FPL fields. [14]

## Source comparison

| Source | Data for Scout mode | Access | Terms of use / robots | Freshness | v1? |
|---|---|---|---|---|---|
| **FPL API** `bootstrap-static` | Per Footballer: `status` (a/d/i/s/u/n), `news`, `news_added`, chance of playing this and next round, `scout_risks`, `scout_news_link` [1] | Public JSON, no auth, about 1.8 MB [1] | Site robots.txt returns the app's HTML, so there is no robots file [F, 1]. FPL terms claim IP in "any Game data" and require written consent for use [14]. No published API terms. | Today's `news_added` stamps all fall at :00:05 or :30:05 [F, 1], which suggests a half-hourly publish cycle [I] | **Yes** (core) |
| **Premier League injury page** `premierleague.com/en/latest-player-injuries` | Club-by-club injury list, "Last updated 17:07 GMT, 19 November 2026" [2] | The HTML has no data. A JS widget (`injury-news/injury-news`) loads it from an undocumented Pulselive API [F, 2] | robots.txt only blocks query parameters [F]. Terms: "private and personal use"; must not "reproduce, re-utilise or redistribute"; no "creating a database"; no commercial use [5] | Same day [2] | No. Likely duplicates the FPL `news` field [I] |
| **Club sites** (e.g. tottenhamhotspur.com, avfc.co.uk, arsenal.com) | Pre-match team-news articles and press-conference write-ups. FPL already links to them through `scout_news_link` (62 Footballers today, 15 club domains) [1] | HTML only. The RSS paths tried returned HTML or 404 [F] | robots.txt files are mostly permissive [F]. Spurs terms (cl. 4.1, 4.6.3, 4.6.4): "personal and non-commercial use only"; no "scraping, crawling… bots"; no use "to generate prompts… in training AI models or any other form of automated content generation" [13] | 1–2 days before the match | No to fetching. **Yes to passing the link** to Members as "read more" [I] |
| **BBC Sport RSS** `feeds.bbci.co.uk/sport/football/premier-league/rss.xml` | 51 items, mostly general PL stories. Each has about 150 characters of description [F, 3] | Public RSS | robots.txt header bans scraping, RAG, "agentic AI", and "using BBC content to create summaries for your own use" [3]. Terms §8: permission needed for "anything plucked from our services… to do computer analysis". §15: "not allowed to pluck metadata from our… RSS feeds" [4] | Hourly | **No** |
| **Guardian Open Platform** (free developer key) | Full article text, 500 calls/day, 1 call/sec, non-commercial [6] | Needs a registered key | Terms 6(g): must not use content "with any machine learning and/or artificial intelligence technologies to generate any data or content". robots.txt says the same [7][8] | Live | **No** |
| **Reddit** (r/FantasyPL) | Community leaks, press-conference transcripts | OAuth only. Free tier is 100 queries/min per client. Since Nov 2025, new access needs approval [10][11][12] | robots.txt: `Disallow: /` and points to the Public Content Policy [F, 9]. Responsible Builder Policy: no unapproved commercialisation or AI training [11] | Minutes | **No** (needs app registration and approval) |
| **Fantasy Football Scout** (team news, predicted line-ups) | Live injury blogs and early team news for all 20 clubs [F, feed] | RSS at `/feed/` has 12 items with excerpts [F] | Terms cl. 6.6: must not "make mass, automated or systematic extractions". cl. 6.2.1: "personal, non-commercial use" [15] | Several posts a day | **No** |
| **Fantasy Football Hub** (predicted line-ups) | Predicted line-ups and team news | HTML | Terms 6.6.1–6.6.2 (updated 3 Jul 2026) ban "bots, scripts" and "any form of data scraping… for personal use" [16] | Daily | **No** |
| **Sportsgambler** (injuries and predicted line-ups) | Injury and line-up tables | HTML, sitemaps published | Terms (updated 30 Jan 2026) ban "bots, scrapers, crawlers, spiders or data-mining tools" without written permission. They do allow sharing links [17] | Daily | **No** |
| **YouTube** (press-conference videos) | Video metadata only | Data API key | `captions.download` "requires the user to have permission to edit the video", so other people's captions are unavailable. It costs 200 quota units per call [18] | Live | No (no transcripts) |

Not checked in depth: RotoWire (terms URL returned 404), Sports Mole, Man City and Chelsea terms, and X/Twitter. All of them are third-party editorial or user content. **[I]** The same pattern of personal-use terms with an AI or scraping ban very likely applies.

## Recommended v1 sources

1. **FPL `bootstrap-static`** (required). Read `status`, `news`, `news_added`, `chance_of_playing_*`, `scout_risks` and `scout_news_link`. Analyst mode already fetches this endpoint, so Scout mode needs no new collection code. **[I]**
2. **Member notes** (optional, opt-in). A Member pastes or types team news they read themselves, such as a press-conference quote, before a cut-off. **[I]** This is the only unstructured input that needs no third-party licence for automated or AI processing.
   - The Member chose to read it and to share it. The bot never fetches the source.
   - Cap the length, for example 1,500 characters per Member per Gameweek. Ask for the gist, not whole articles. That keeps tokens bounded and avoids copying copyrighted text in bulk.
3. **`scout_news_link` passthrough**. Show the club's own article link next to any flagged Footballer in the advice message, so the Member can read it themselves. **[I]** The bot never fetches it.

Deferred, each needing its own permission or licence: BBC, the Guardian (commercial or AI licence), Reddit (approved app), and FFS, FF Hub or Sportsgambler (written consent).

## Pre-filter pipeline design (v1)

Goal: Claude reads team news **once per Gameweek**, and only what plain code cannot resolve. Every stage before Claude is deterministic code.

```
[1 Snapshot] -> [2 Pool filter] -> [3 Diff] -> [4 Parse & classify] -> [5 Residue pack] -> Claude -> [6 Apply]
```

1. **Snapshot** `bootstrap-static` on a schedule, keeping only the news columns (about 10 fields × 672 Footballers).
   - Today's `news_added` stamps all fall on :00 or :30 [1], so polling every 30 minutes is enough. **[I]**
   - Use a generic User-Agent and stay low-rate: one request every 30 minutes, and only in the 48 hours before the deadline.
2. **Pool filter.** Keep a Footballer if he is in any of these groups:
   - any Member's Squad
   - any Member's Watch list
   - the top N by Elite ownership (e.g. N=60, or ≥5% in the top-10k Elite cohort)
   - the Footballers behind any open Gap, Elite or Rival
   - starters likely to be picked as transfer-in candidates (top xP by position)

   Today a pool of about 120 Footballers held 24 flagged records. [F, simulated on [1] using overall ownership as a proxy]
3. **Diff** against the last snapshot Claude read. Key on `(id, status, news, chance_next, scout_risks)`. Only changed or new records go forward. This step removes repeats: a record Claude already read is never sent again. **[I]**
   - Today, 16 of those 24 records had changed since the GW10 deadline (6 Nov). That window covers an international break, so a normal week should have fewer. [F/I]
4. **Parse and classify with regex**, no Claude. These templates covered every entry today [F, 1]:
   - `^(?P<reason>.+?) - (?P<pct>\d+)% chance of playing$` → minutes multiplier = pct/100
   - `- Unknown return date$` → out (0 minutes); flag for review after N Gameweeks
   - `- Expected back (?P<date>\d+ \w+)$` → out until the Gameweek that contains the date
   - `^Suspended until (?P<date>…)$` → out until that date (`status = s`)
   - `^Has joined .+ (on loan|permanently)|departed the club` → removed (`status = u`)
   - `scout_risks`: `suspension_risk` (one more yellow card means a 1-match ban), `loan_ineligible` (out for Gameweek *g*) [1]

   Records that match are applied straight to minutes and xP in Analyst mode. They are **logged and shown to Members, but never sent to Claude**. **[I]**
5. **Residue pack** for Claude. It contains:
   - (a) FPL records that matched no template, or where status and text disagree, for example `status = d` with no percentage, or "Unspecified injury" on a high-Elite-ownership Footballer
   - (b) Member notes, cut down by code first:
     - drop sentences that name no Footballer in the pool (match against `web_name`, `first_name` and `second_name`, accent-insensitive)
     - keep sentences that hit a keyword list: *fit, available, doubt, injur*, knock, scan, ruled out, assess, return, back in training, minutes, rotate, start, bench, suspend*, ill*
     - drop notes that repeat a Footballer already covered by a matched FPL record, unless the note contradicts it
   - (c) the current baseline per Footballer: id, name, club, position, baseline minutes and xP

   One line per Footballer, pipe-separated, no JSON keys. The instructions are fixed text, so cache them as a prompt prefix.
6. **Claude output**: strict JSON with `[{id, minutes_multiplier, confidence, source: "fpl"|"note", reason≤15 words}]`. Code checks the ranges (0–1.0) and applies them. Claude never writes final numbers outside these fields, which matches Analyst mode.

### Token estimate per Gameweek

Token counts use the chars/4 rule of thumb. Confirm them with a real tokenizer when this is built. **[I]**

| Item | Size | ~Tokens |
|---|---|---|
| Fixed instructions and output schema (cacheable) | about 2,000 characters | ~500 |
| FPL residue (unparsed or contradictory), usually 0–10 records × ~60 characters | — | 0–150 |
| Changed FPL records sent for context (16–20 today × ~60 characters) | 963–1,159 characters [F, simulated] | 240–290 |
| Member notes after the filter (e.g. 5 Members × ≤600 characters kept) | ≤3,000 characters | ≤750 |
| Baseline xP and minutes lines (≤40 Footballers × ~30 characters) | ≤1,200 characters | ≤300 |
| **Input total** | | **~1.0k–2.0k** |
| Output JSON (≤40 rows × ~25 tokens) | | **~0.3k–1.0k** |
| **Per Gameweek, one read** | | **~1.5k–3k** |

The same data without the filter, for comparison [F, measured on [1]]:
- all 197 news entries in compact lines: 12,171 characters, about 3k tokens
- the same entries as JSON with keys: 45,410 characters, about 11k tokens
- the full `bootstrap-static`: 1.8 MB, about 450k tokens

**[I]** Without Member notes, stage 4 usually leaves nothing for Claude. Scout mode could then skip the Claude call that Gameweek and cost 0 tokens.

## Open questions

1. **Is Scout mode worth Claude at all in v1?** On FPL-only data, stage 4 settles nearly everything. Options:
   - (a) ship Scout mode as deterministic parsing plus a Claude pass over Member notes only
   - (b) fold FPL news parsing into Analyst mode, and keep Scout mode for Member notes and any future licensed source

   This is a product decision.
2. **FPL terms and "Game data".** The terms reserve IP in "any Game data" and require written consent. [14] This applies to the whole bot, not only Scout mode. Do we accept the same risk as the many open-source FPL tools, or ask the Premier League?
   - The terms page is a JS app and could not be fetched. This quote comes from a search-engine capture of `fantasy.premierleague.com/help/terms`. Verify it by hand in a browser.
3. **How much does the `news` field lag press conferences?** Measure `news_added` against press-conference times for a few Gameweeks. If FPL updates within a few hours, Member notes add little.
4. **Member notes and copyright.** Should the bot store pasted text, or only Claude's structured output? **[I]** Store only the output plus a hash, and delete the raw notes after the deadline.
5. **Worth asking for permission?** One email to Fantasy Football Scout or Sportsgambler asking for written consent for a small, private, non-commercial group could unlock predicted line-ups. Who would send it, and is it worth doing?
6. **Rival Squads in the pool.** Rival Squads are only visible after the deadline, so they can't sharpen the pre-deadline pool. Use the previous Gameweek's Rival Squads as a proxy?

## Sources

1. FPL API `bootstrap-static`, fetched 2026-11-19 (672 elements; fields `news`, `status`, `chance_of_playing_*`, `scout_risks`, `scout_news_link`; events 10/11): https://fantasy.premierleague.com/api/bootstrap-static/ (robots: https://fantasy.premierleague.com/robots.txt returns the app's HTML)
2. Premier League injury page and its HTML widgets (`injury-news/injury-news`, `sdp-prem-prod.premier-league-prod.pulselive.com/api`): https://www.premierleague.com/en/latest-player-injuries (robots: https://www.premierleague.com/robots.txt)
3. BBC robots.txt (AI/RAG/summaries header): https://www.bbc.co.uk/robots.txt. BBC Sport PL feed: https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml
4. BBC Terms of Use v1.8, §8 and §15: https://www.bbc.co.uk/usingthebbc/terms-of-use/. Business use of RSS: https://www.bbc.co.uk/usingthebbc/terms/can-i-use-bbc-content-for-my-business/
5. Premier League Terms of Use ("Intellectual property rights", "Your lawful use"): https://www.premierleague.com/en/terms-and-conditions
6. Guardian Open Platform access tiers: https://open-platform.theguardian.com/access/
7. Guardian Open Platform terms, §4(b) and §6(g): https://www.theguardian.com/open-platform/terms-and-conditions
8. Guardian robots.txt header: https://www.theguardian.com/robots.txt
9. Reddit robots.txt: https://www.reddit.com/robots.txt
10. Reddit Data API Wiki (100 QPM per OAuth client; non-OAuth traffic blocked). The page returned 403 to the fetcher, so this is read from search-engine captures of the page: https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki
11. Reddit Responsible Builder Policy (approval required; no unapproved commercialisation or AI training). Also read from search-engine captures: https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy
12. r/redditdev announcement "Introducing the Responsible Builder Policy", 11 Nov 2025: self-service API access closed. Read via a mirror, because reddit.com blocks fetchers: https://r.datuan.dev/r/redditdev/comments/1oug31u/introducing_the_responsible_builder_policy_new/noc31sg
13. Tottenham Hotspur website terms, cl. 4.1, 4.6.3, 4.6.4, 4.10, 7.2: https://www.tottenhamhotspur.com/information/terms-and-conditions
14. FPL Terms & Conditions (IP in "any Game data"). The page is a JS app, so this is read from a search-engine capture; verify by hand: https://fantasy.premierleague.com/help/terms
15. Fantasy Football Scout terms, cl. 6.2 and 6.6: https://www.fantasyfootballscout.co.uk/terms-and-conditions. Feed: https://www.fantasyfootballscout.co.uk/feed/. robots: https://www.fantasyfootballscout.co.uk/robots.txt
16. Fantasy Football Hub terms (updated 3 Jul 2026), cl. 6.2, 6.6, 6.7: https://www.fantasyfootballhub.co.uk/terms-and-conditions
17. Sportsgambler terms (updated 30 Jan 2026): https://www.sportsgambler.com/terms-and-conditions/. robots: https://www.sportsgambler.com/robots.txt
18. YouTube Data API `captions.download`: https://developers.google.com/youtube/v3/docs/captions/download
