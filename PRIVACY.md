# Privacy

The bot is invite-only and run by one owner for a small group of Members. This page lists what
the owner's instance stores and how to remove it. A fork run by someone else is their
responsibility.

## What is stored about a Member

- Your **FPL team ID** and your **Telegram chat ID**.
- Your **Goal** and the **league IDs** you chose to follow (your Followed leagues).
- Your **Watch list** (Footballers you are thinking of buying).
- Your **timezone** and **Price alert time**.
- Your FPL team's public history and picks, fetched from the official FPL API.
- Invite codes, stored only as hashes.

The bot also stores the public picks of **Rivals** (other managers in your Followed leagues) for
the current season. They are deleted when no Member follows that league any more, and cleared at
the season rollover.

## What is not stored or sent

- No raw FPL API responses, and no IDs or picks of the sampled top-ranked managers: only
  aggregated ownership figures.
- No usage telemetry or analytics.
- Logs identify Members only by an internal number, never by chat ID, team ID or name.
- Messages from chats that are not Members are ignored and not stored.
- In Phase 1 nothing is sent to Claude or any other AI service. When explanations arrive later,
  prompts carry no Member identifiers or team names.

## Where it lives

- The database is [Neon](https://neon.tech) Postgres in the EU. The bot runs on
  [Railway](https://railway.com) in the EU.
- Messages pass through Telegram, under Telegram's own privacy policy.
- A nightly encrypted backup of the Member tables (Members, invites, Watch lists, Goals) is sent to
  the owner's own Telegram chat. Only the owner holds the decryption key. The last 7 are kept.

## Deleting your data

Send `/leave` to the bot. After one confirmation it immediately and permanently deletes your
Member record, Goal, Followed leagues, Watch list, timezone and stored team data. Rival picks kept
only for your leagues are deleted once no other Member follows them.

Copies can survive for a short time outside the live database:

- Neon keeps a point-in-time restore history for a short window (on the free plan, hours to about
  a day, per Neon's current plan limits), after which deleted rows are gone.
- The encrypted nightly backups in the owner's chat roll over within 7 days.

## Contact

Message the owner who invited you. For security issues, see [SECURITY.md](SECURITY.md).
