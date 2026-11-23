# Free hosting, database and scheduling options

Type: research
Status: resolved
Blocked by: —

## Question

What free-tier stack can run the system 24/7 with no spend? The system is:
- a Python service
- scheduled jobs (price snapshots several times a day, a nightly Price alert per Member timezone, deadline-relative runs)
- a Telegram bot (webhook or polling)
- a Postgres or SQLite store
- later, a TypeScript web dashboard

Compare, for example:
- GitHub Actions cron
- Oracle Cloud Always Free
- Fly.io
- Render
- Railway
- Koyeb
- Cloudflare Workers/Cron
- Google Cloud Run free tier
- Neon or Supabase free Postgres
- Vercel or Cloudflare Pages for the dashboard

For each, note limits: sleep or cold starts, cron precision, monthly hours, egress, card requirement, and secret storage. Note any that block calls to the FPL API or block Telegram. Recommend one stack and a backup.

Findings go in `.scratch/fpl-bot/research/09-free-hosting-and-scheduling.md`.

## Answer

- **Primary:** an Oracle Cloud Always Free Ampere A1 VM (up to 2 OCPU / 12 GB, 10 TB egress) runs one always-on Python process. That process holds an in-process scheduler (price snapshots, per-Member-timezone Price alerts, deadline-relative runs) and the Telegram bot in long-polling mode, so no inbound port or TLS is needed. Signup needs a card for verification. Watch out for Oracle's 7-day idle-reclamation rule.
- **Store:** Neon free Postgres (no card, 1 GB per project, 100 CU-h/month, no inactivity deletion). This keeps the VM stateless so it can fail over. Supabase pauses free projects after 1 week of inactivity, which is risky in the off-season.
- **Backup host:** a Google Cloud e2-micro Always Free VM (US regions, 1 GB RAM, billing account required) running the same container against the same Neon DB.
- **Dashboard (later):** Cloudflare Pages or Workers static assets (free, unlimited static requests). Vercel Hobby cron is daily only, ±59 min.
- **GitHub Actions:** use it for CI only. It's free for public repos, but schedules are best-effort (5-min minimum, disabled after 60 days without repo activity). Community reports show 2–6 h delays and drops in Aug–Oct 2026, and GitHub's terms bar using hosted runners for things unrelated to building or testing the project.
- **Ruled out:** Fly.io (no free tier for new orgs), Render (15-min spin-down, no free cron, Postgres expires after 30 days), Railway ($1/month credit, sleeps), Koyeb (0.1 vCPU web-only, scales to zero after 1 h, card with $29 hold). Cloudflare Workers is only good for glue (10 ms CPU, 5 cron triggers).
- **FPL access risk (community-reported):** FPL has intermittently returned 403 to cloud IPs (AWS Lambda, Oct 2026), and some paths reject a bare Python UA. Send a browser User-Agent, don't retry 403s, and curl-test from the chosen host before committing.

Findings: [../research/09-free-hosting-and-scheduling.md](../research/09-free-hosting-and-scheduling.md)
