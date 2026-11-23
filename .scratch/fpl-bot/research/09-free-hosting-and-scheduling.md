# Free hosting, database and scheduling options

Research for ticket `issues/09-free-hosting-and-scheduling.md`. Researched 2026-11-19. Free tiers change often. Each claim cites the page it came from, with the page's own date where one was shown ("no date" means the page showed none).

## TL;DR

- **Best fit for "24/7 at no cost": one always-on Always Free VM.** Use Oracle Cloud Always Free Ampere A1 (up to 2 OCPU / 12 GB in Always Free tenancies, 10 TB/month egress) running one Python process. That process holds the scheduler (price snapshots, per-Member-timezone Price alerts, deadline-relative runs) and the Telegram bot in long-polling mode. [OCI Always Free]
- **Oracle has two real gotchas.** Signup needs a card for verification (not charged unless you upgrade). Oracle may also reclaim "idle" instances: 95th-percentile CPU < 20%, network < 20% and (for A1) memory < 20% over 7 days. A lightly loaded bot can match all three. [OCI signup] [OCI Always Free]
- **Store: Neon free Postgres.** No card, 1 GB per project, 100 CU-hours per project per month, scale-to-zero after 5 minutes, and no pausing or deletion for inactivity. That keeps the VM stateless, so moving to the backup host is just "start the container elsewhere". [Neon pricing, updated 2026-11-04]
- **Don't make GitHub Actions cron the main scheduler.** Standard runners are free for public repos. But the docs say schedules "can be delayed" under load, the minimum interval is 5 minutes, and scheduled workflows are disabled after 60 days without repo activity. Community threads from Aug–Oct 2026 report runs **2–6 hours late or dropped**. GitHub's Actions terms also bar GitHub-hosted runners from activity "unrelated to the production, testing, deployment, or publication of the software project" and from being "part of a serverless application". [GH events] [GH billing] [GH terms] [community #207346]
- **The other PaaS free tiers don't fit an always-on bot plus scheduler.** Fly.io has no free tier for new orgs. Render's free web services spin down after 15 minutes, it has no free cron or worker types, and free Postgres expires after 30 days. Railway Free is $1/month of usage and is meant for apps that "sleep when idle". Koyeb gives one 0.1 vCPU web-only instance that scales to zero after 1 hour, and needs a card with a $29 hold. [Fly] [Render] [Railway] [Koyeb instances] [Koyeb FAQ]
- **Cloudflare Workers is free and always on, but only suits thin glue, not the Python service.** It allows 10 ms CPU per invocation (cron included), 5 cron triggers per account, and UTC-only cron. A good use is an external "pinger" that triggers jobs on time. [CF limits] [CF cron]
- **Dashboard: Cloudflare Pages or Workers static assets** (static requests "free and unlimited", 500 builds/month). Vercel Hobby also works, but Hobby cron is limited to once per day with ±59 min precision. [CF pricing] [CF Pages limits] [Vercel cron]
- **FPL blocking cloud IPs is real but intermittent (community-reported).** One AWS Lambda project saw intermittent 403s from FPL in October 2026 that cleared within the day, made worse by retrying 403s. Some FPL paths also 403 a bare Python/curl User-Agent. No report found specifically for Oracle, GitHub Actions or Cloudflare IPs. **Test from the chosen host before committing.** [fpl-stats #217] [fpl-api repo]
- **Telegram itself is not blocked by any of these hosts** as far as found. Long polling needs no inbound ports or TLS. Webhooks only accept ports 443, 80, 88 and 8443. [Telegram Bot API]

## Comparison table

"n/s" = the fetched official page doesn't say.

| Option | What's free | Sleep / cold start | Cron precision | Hours / quotas | Egress | Card | Secrets | Fit |
|---|---|---|---|---|---|---|---|---|
| **GitHub Actions** (public repo) | Standard hosted runners free in public repos [GH billing] | Each job is a fresh runner (no long-lived process) | Min every 5 min, UTC by default with optional IANA timezone; "can be delayed" under load; disabled after 60 days without repo activity [GH events]. Community: 2–6 h delays and drops Aug–Oct 2026 [#207346] | 6 h per job, 20 concurrent jobs [GH limits] | n/s | No | Repo/env/org secrets; > 48 KB needs a workaround; not passed to fork PR workflows [GH secrets] | Batch jobs and CI only. ToS risk for running production jobs [GH terms] |
| **Oracle Cloud Always Free** | 2× AMD micro (1/8 OCPU, 1 GB) and A1 Arm 1,500 OCPU-h + 9,000 GB-h/month = 2 OCPU / 12 GB; 200 GB block; 20 GB object storage; 2 Autonomous DBs (20 GB each) [OCI Always Free, no date] | None (real VM); idle instances may be reclaimed [OCI Always Free] | Whatever you run (cron/APScheduler, minute-level or better) | Always on | 10 TB/month [OCI Always Free] | Yes, verification hold, not charged unless you upgrade [OCI signup] | Self-managed on the VM | **Primary** |
| **Fly.io** | "New organizations don't have a free tier"; trial $1 credit for 7 days [Fly] | Auto-stop possible | Self-run | Smallest machine $2.19/month [Fly] | $0.02/GB NA/EU [Fly] | Yes after the trial [Fly] | n/a | No (not free) |
| **Render** | 750 free instance-hours/month per workspace; web services, Postgres, Key Value, static sites only [Render] | Spins down after 15 min without inbound traffic; ~1 min spin-up [Render] | No free cron jobs or workers [Render] | Services suspended when hours run out [Render] | Counts against included bandwidth; suspension if over with no card [Render] | n/s | n/s | No |
| **Railway** | Free plan: $1 usage/month; Trial: one-time $5 [Railway] | Free plan is for apps that "sleep when idle" [Railway] | Cron ≥ 5 min apart, UTC, can "vary by a few minutes" [Railway cron] | 0.5 GB RAM, 1 vCPU per service on Free [Railway] | $0.05/GB [Railway] | Free plan: "no credit card" [Railway] | n/s | No ($1 won't cover 24/7) |
| **Koyeb** | 1 free web service (0.1 vCPU, 512 MB, 2 GB SSD), Frankfurt or Washington DC; free Postgres limited to 5 h active time, 1 GB [Koyeb instances, updated 2026-05-27] [Koyeb FAQ] | Scales to zero after 1 h without traffic; web services only, no workers [Koyeb instances] | None built in | — | 100 GB/month [Koyeb FAQ] | Yes, $29 pre-auth hold [Koyeb FAQ] | n/s | No. Note: FAQ banner says Koyeb is joining Mistral AI [Koyeb FAQ] |
| **Cloudflare Workers + Cron** | 100k requests/day; KV, D1 (5 GB, 5M rows read/day), Queues free [CF pricing, modified 2026-11-18] | No sleep (isolates) | Cron in UTC, minute granularity; changes take up to 15 min to propagate and runs can be missed meanwhile [CF cron] | 10 ms CPU per invocation (HTTP and cron); 15 min wall time for cron; 5 cron triggers per account; 50 subrequests [CF limits] | n/s | n/s | n/s on the fetched pages | Glue / precise trigger / Telegram webhook only. Python Workers exist (page modified 2026-09-17) [CF Python] |
| **Google Cloud Run** | 2M requests, 180k vCPU-s, 360k GB-s, 1 GB NA egress per month [GCP free] | Scales to zero (cold starts) | Via Cloud Scheduler: 3 free jobs per billing account, $0.10/job/31 days after [Cloud Scheduler pricing] | — | 1 GB/month from North America [GCP free] | Billing account required [GCP free] | Secret Manager: 6 active versions, 10k accesses free [GCP free] | Possible, but only 3 free scheduler jobs and a billing account |
| **Google Compute e2-micro** (Always Free) | 1 e2-micro in us-west1 / us-central1 / us-east1, 30 GB disk [GCP free] | None (VM) | Self-run | Always on | 1 GB/month from North America [GCP free] | Billing account required [GCP free] | Self-managed | **Backup host** |
| **Neon** (Postgres) | 100 projects; 1 GB per project (20 GB total); 100 CU-h per project per month [Neon, updated 2026-11-04] | Compute suspends after 5 min idle; resumes on connect [Neon] | — | Compute stops if CU-h or egress run out, resumes next period [Neon] | 5 GB/month per project [Neon] | No [Neon] | Connection string | **Store** |
| **Supabase** (Postgres) | 500 MB DB, 5 GB egress, 2 active projects, 500k Edge Function calls [Supabase pricing] | Projects "paused after 1 week of inactivity" [Supabase pricing] | — | — | 5 GB [Supabase pricing] | n/s | — | Backup store only (pausing risk) |
| **Vercel Hobby** (dashboard) | 100 GB transfer, 1M function invocations, 4 CPU-h active CPU [Vercel Hobby, updated 2026-11-12] | Functions (serverless) | Cron once per day, ±59 min [Vercel cron, updated 2026-07-15] | Over limit: usually wait 30 days [Vercel Hobby] | 100 GB [Vercel Hobby] | No for Hobby (card only when upgrading) [Vercel Hobby] | n/s | Dashboard OK; not for scheduling |
| **Cloudflare Pages / static assets** (dashboard) | Static asset requests free and unlimited [CF pricing]; 500 builds/month, 1 concurrent build, 20k files [CF Pages limits, modified 2026-11-18] | No sleep | — | Functions count against the Workers quota [CF Pages limits] | n/s | n/s | n/s | **Dashboard** |

## Recommended stack

**Primary: Oracle Always Free A1 VM + Neon + Cloudflare for the dashboard**

1. **Compute:** one Oracle Always Free `VM.Standard.A1.Flex` (Arm) in the home region. [OCI Always Free] It runs a single Python process (or a docker-compose of one service) containing:
   - an in-process scheduler for price snapshots several times a day, the nightly **Price alert** per **Member** timezone, and deadline-relative runs per **Gameweek**. An always-on process gives exact, timezone-aware timing and none of the delay or drop problems of hosted cron.
   - the Telegram bot in **long-polling** mode (`getUpdates`). No public port, TLS cert or domain is needed. Telegram keeps undelivered updates for up to 24 h, so a restart loses nothing. [Telegram Bot API]
2. **Store:** Neon free Postgres. The VM holds no state, Neon has no inactivity deletion, and it needs no card. Scale-to-zero after 5 min means a cold connect on the first query after idle; that's fine for this workload. [Neon]
3. **Dashboard (later):** Cloudflare Workers static assets or Pages for the TypeScript front end. Static assets are free and unlimited, there is no sleep, and any API calls go back to the VM or Neon. [CF pricing] [CF Pages limits]
4. **CI:** GitHub Actions (free for the public repo) for tests and building the Arm image. This is squarely "production, testing, deployment" use under GitHub's terms. [GH billing] [GH terms]

Why: it's the only option found that is always on, has generous RAM for pandas/xP models (12 GB), allows minute-precise per-timezone scheduling, has effectively no egress worry (10 TB), and needs no inbound networking. The cost is a card for verification and having to guard against idle reclamation.

**Backup: Google Cloud e2-micro Always Free VM (same container) + the same Neon DB**

- Because the store is external, failover is "deploy the same image to the other VM". An e2-micro (US regions, 30 GB disk) is always on. [GCP free] Watch three things: only 1 GB of RAM, so keep the model code lean or add swap; 1 GB/month North America egress (Telegram messages are small); and a required billing account. [GCP free]
- **Second-line fallback with no VM at all:** GitHub Actions scheduled workflows for the batch jobs (snapshots, xP, Price alerts), with `workflow_dispatch` fired by a Cloudflare Worker cron for on-time starts. This is the community-recommended workaround for late schedules. Interactive bot replies would then need a webhook endpoint, such as a Cloudflare Worker, and that endpoint must stay under 10 ms CPU. [#207346] [CF limits] [Telegram Bot API] Treat this as an emergency mode only, because of the ToS clause and the reliability reports. [GH terms]

## Gotchas

- **Oracle idle reclamation.** The idle test is CPU p95 < 20%, network < 20% and memory < 20% (A1) over 7 days. Plan for it: either keep a legitimate always-running workload, or check whether upgrading to Pay-As-You-Go avoids reclamation. Always Free resources stay free after upgrading ("Oracle doesn't charge for Always Free resources after you upgrade"), but a PAYG account can incur charges by mistake. [OCI Always Free]
- **Oracle "out of host capacity".** Always Free A1 shapes can be temporarily unavailable in your home region. Compute must be in the home region, which is chosen at signup, so pick a region close to the UK (FPL) carefully. [OCI Always Free]
- **GitHub Actions schedules are best effort.** Officially: delays under load, 5-minute minimum, default branch only, auto-disabled after 60 days without activity in a public repo. That last one hits in the off-season (late May to August), when the repo may get no commits. [GH events] Community reports from Aug–Oct 2026: 2–6 h delays, dropped slots, new schedules never firing, and no staff response in the thread. [#207346]
- **GitHub Actions terms.** Hosted runners must not be used for activity "unrelated to the production, testing, deployment, or publication of the software project", or "as part of a serverless application". Running the live bot's jobs on Actions is a grey area at best. [GH terms]
- **Cloudflare Workers 10 ms CPU.** `bootstrap-static` was about 1.8 MB of JSON when checked on 2026-11-19 (`content-length: 1797902`). Parsing and analysing it inside a free Worker's 10 ms CPU budget is unlikely, so keep Workers to triggering and routing. [CF limits]
- **FPL 403s from cloud IPs (community-reported).** In jake-thewoz/fpl-stats #217 (opened 2026-10-11), FPL returned intermittent 403s to an AWS Lambda while a home connection worked; it cleared by end of day. The author suspected AWS-range blocking plus self-inflicted bursts from retrying 403s. Proposed fixes: don't retry 403, serve stale cache, alert on 403 spikes, cache longer. [fpl-stats #217] jakesmith1997-sfc/fpl-api (probed 2026-08-29) says to send a browser `User-Agent` because "some paths 403 a bare Python/curl UA". No official rate limit is published. [fpl-api repo] Analogous datacenter-IP blocks on GitHub Actions runners have been reported for other CloudFront-fronted APIs (Fast-F1 #988), but not for FPL. [Fast-F1 #988]
- **FPL's CDN.** Response headers fetched from a home connection on 2026-11-19 showed `x-served-by: cache-…`, `x-timer`, `via: 1.1 google, 1.1 varnish`, with `cache-control: max-age=300`. This is consistent with Fastly in front of a Google origin (an inference from the headers). Cached for 5 minutes, so polling faster than that gains nothing. [observed: `curl -I https://fantasy.premierleague.com/api/bootstrap-static/`]
- **Render / Koyeb / Railway sleep.** A sleeping service can't run a scheduler or poll Telegram, and keep-alive pings to dodge spin-down burn the monthly hours on Render. [Render] [Koyeb instances] [Railway]
- **Supabase pausing.** Free projects pause after 1 week of inactivity, which is risky during the off-season. Neon doesn't pause or delete for inactivity. [Supabase pricing] [Neon]
- **Neon quota.** 100 CU-hours per project per month. If the VM holds a connection open 24/7, compute never scales to zero. Use short-lived connections or a pool with an idle timeout so it can suspend. [Neon]
- **Telegram webhooks** only accept ports 443, 80, 88 and 8443, and should use `secret_token` to verify the sender. Webhook and `getUpdates` are mutually exclusive. [Telegram Bot API]
- **Vercel Hobby cron** is once per day with ±59 min precision. Don't use it for Price alerts. [Vercel cron]

## Open questions

1. Does FPL return 200 to the chosen Oracle region's IPs (and to Google, Cloudflare and GitHub runner IPs)? This needs a one-off `curl` test from each host with a browser `User-Agent`. No community report covered these providers specifically.
2. Does an Oracle Pay-As-You-Go upgrade exempt Always Free instances from idle reclamation? The Always Free page doesn't say. Weigh that against the risk of accidental charges.
3. Do Cloudflare Workers and Pages free plans need a card? The fetched pages don't say.
4. Which Oracle home region? A1 capacity varies by region, and the choice is permanent for Always Free.
5. Will the xP/model code fit in 1 GB RAM if the e2-micro backup ever has to carry the full load?
6. Vercel's fair-use page sections ("Examples of fair use" / "Never fair use") were empty in the fetched copy, so whether a free group bot's dashboard is fine on Hobby couldn't be confirmed. Cloudflare avoids the question.

## Sources

- [OCI Always Free] Oracle, Always Free Resources (no date): https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- [OCI signup] Oracle, Sign Up for Oracle Cloud Free Tier (no date): https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm
- [GH billing] GitHub Actions billing (no date): https://docs.github.com/en/billing/concepts/product-billing/github-actions
- [GH events] GitHub, Events that trigger workflows, `schedule` (no date): https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- [GH limits] GitHub Actions limits (no date): https://docs.github.com/en/actions/reference/limits
- [GH secrets] GitHub, Using secrets (no date): https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- [GH terms] GitHub Terms for Additional Products and Features, Actions (no date): https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
- [#207346] GitHub Community Discussion #207346, scheduled runs dropped/delayed since 2026-08-26 (community-reported, Sep–Oct 2026): https://github.com/orgs/community/discussions/207346
- [Fly] Fly.io pricing (no date): https://docs.fly.io/about/pricing
- [Render] Render, Deploy for Free (no date): https://render.com/docs/free
- [Railway] Railway plans (no date): https://docs.railway.com/reference/pricing/plans
- [Railway cron] Railway cron jobs (no date): https://docs.railway.com/reference/cron-jobs
- [Koyeb instances] Koyeb instances reference (updated 2026-05-27): https://www.koyeb.com/docs/reference/instances
- [Koyeb FAQ] Koyeb pricing FAQ (updated 2026-05-27): https://koyeb.com/docs/faq/pricing
- [CF limits] Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/
- [CF pricing] Cloudflare Workers pricing (modified 2026-11-18): https://developers.cloudflare.com/workers/platform/pricing/
- [CF cron] Cloudflare Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- [CF Python] Cloudflare Python Workers (modified 2026-09-17): https://developers.cloudflare.com/workers/languages/python/
- [CF Pages limits] Cloudflare Pages limits (modified 2026-11-18): https://developers.cloudflare.com/pages/platform/limits/
- [GCP free] Google Cloud Free Tier features (no date): https://docs.cloud.google.com/free/docs/free-cloud-features
- [Cloud Scheduler pricing] Google Cloud Scheduler pricing (via search snippet of the official page; full page didn't render): https://cloud.google.com/scheduler/pricing
- [Neon] Neon pricing (updated 2026-11-04): https://neon.com/pricing
- [Supabase pricing] Supabase pricing (no date): https://supabase.com/pricing
- [Vercel Hobby] Vercel Hobby plan (updated 2026-11-12): https://vercel.com/docs/plans/hobby
- [Vercel cron] Vercel cron jobs usage & pricing (updated 2026-07-15): https://vercel.com/docs/cron-jobs/usage-and-pricing
- [Telegram Bot API] Telegram Bot API, getUpdates / setWebhook: https://core.telegram.org/bots/api
- [fpl-stats #217] jake-thewoz/fpl-stats issue #217, FPL intermittent 403 to AWS Lambda (community-reported, 2026-10-11): https://github.com/jake-thewoz/fpl-stats/issues/217
- [fpl-api repo] jakesmith1997-sfc/fpl-api endpoint reference (community, probed 2026-08-29): https://github.com/jakesmith1997-sfc/fpl-api
- [Fast-F1 #988] theOehrly/Fast-F1 issue #988, GitHub Actions runners blocked by CloudFront (community-reported, analogous, not FPL): https://github.com/theOehrly/Fast-F1/issues/988
- Not used as evidence: Cloud Run's own pricing page (https://cloud.google.com/run/pricing) didn't render. Cloud Run figures come from the GCP Free Tier page above.
