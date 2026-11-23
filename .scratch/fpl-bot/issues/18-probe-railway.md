# Probe Railway: FPL reachability and solver timing

Type: task
Status: resolved
Assignee: owner
Blocked by: —

## Question

Before ingestion and the transfer planner are designed around Railway (see [Architecture, frameworks and hosting for v1](12-architecture-and-framework.md)), measure two facts from a throwaway probe service in Railway EU West (Amsterdam), deployed on the owner's Hobby account and deleted afterwards:

1. **FPL reachability from Railway's shared outbound IPs:** do `bootstrap-static`, `fixtures`, `event/{gw}/live`, `entry/{id}/event/{gw}/picks` and `leagues-classic/{id}/standings` return 200 with a generic browser-style User-Agent? Repeat over at least 24 hours at a polite rate (≤1 req/s). Record any 403 or 429 responses and when they happen. Never retry a 403.
2. **Solver timing:** how long does upstream open-fpl-solver (pinned commit) take on `highspy` for horizons of 1, 4 and 8 Gameweeks at gap 0 and 0.5%, with 1 and 2 vCPU? Also record peak RAM.

Record the results in the answer: the numbers, the pass/fail verdict on reachability, and a confirmation that the probe service was removed. These feed [Which data the bot collects, how often, and what it keeps](13-data-ingestion-design.md) and the transfer-planner fog.

## Answer

Done by the agent on the owner's Railway account, 19–21 Nov 2026. A throwaway project held two services, both in EU West (Amsterdam, `europe-west4-drams3a`): `reach` (1 vCPU / 0.5 GB) and `bench` (2 vCPU, then 1 vCPU, with 2 GB). The probe code, the Dockerfile and the raw logs are in [probes/18-railway/](../probes/18-railway/). They contain no secrets and no personal details.

### 1. FPL reachability: **PASS**

- **Window:** 45.2 h, from 19 Nov 18:48 to 21 Nov 15:58 UTC. It covered the GW11 deadline (21 Nov 11:00 UTC) and the 12:30 and 15:00 kick-offs.
- **Rate and headers:** one round every 10 minutes, with at least 1.5 s between requests, a generic Chrome User-Agent and no other identifying headers. A 403 would have paused that endpoint for 3 rounds, with no retry. None occurred.
- **Results:** 272 rounds and **1,359 requests, all 200**. There were **zero 403s, zero 429s and zero network errors**. Per endpoint: `bootstrap-static` 272, `fixtures` 272, `event/{gw}/live` 271 (round 1 had no Gameweek yet), `leagues-classic/314/standings` 272, `entry/{id}/event/{gw}/picks` 272. The picks belonged to the public Overall league's leader.
- **Deadline behaviour:** `is_current` flipped to GW11 at about 11:38 UTC. GW11 picks returned 200 from the first post-deadline round onwards, and the live endpoint returned 200 throughout the matches.
- **Egress IP:** one shared address, `152.55.185.205`, for all 45 h (39 hourly checks). The container never restarted.
- **Latency:** p50 8–23 ms and p95 ≤ 43 ms per endpoint, with a maximum of 438 ms.
- **Caching:** FPL's Google/Varnish CDN served almost everything (`x-cache: HIT, HIT` for ≥ 98% of bootstrap, fixtures, live and picks requests). **Standings are the exception:** 179 of 272 were `MISS, MISS`, so they reach FPL's origin. That is where any blocking would bite first, so sample standings sparingly.
- **Limits of the sample:** it was one IP and a low rate. It does not show that a 3 req/s burst, such as the Elite sampler in [Where to get top-1k / 10k / 100k ownership data](03-elite-ownership-sources.md), is safe. Keep the fail-soft adapters, never retry a 403, alert the owner on the first 403, and keep Oracle/GCP as the fallback host from [ADR 0001](../../../docs/adr/0001-railway-and-neon-hosting.md).

### 2. Solver timing

- **Solver:** upstream `solioanalytics/open-fpl-solver` at commit `ec65f5e2b2be34441cb4b2a9efafea1ec0fe3b79`, on Python 3.14.10 with **`highspy` 1.15.1**. Upstream's lockfile pins 1.15.1, not the 1.16 named in ticket 07.
- **Settings:** upstream defaults (decay 0.9, `keep_top_ev_percent` 5, `ev_per_price_cutoff` 30), except `xmin_lb` = 37.5 × horizon. That is upstream's 300 over 8 GW, scaled so short horizons keep the same pool. The pool was 291 of 672 players.
- **xP input:** synthetic, built from FPL's `ep_next` scaled by fixture difficulty per GW, for GW11–18.
- **Squad:** the Overall leader's public GW10 squad, with 2 free transfers and £1.9m in the bank.
- **Measurement:** each solve ran in its own subprocess after a discarded warm-up run. "HiGHS" is HiGHS's own timing. "Wall" is the whole run: imports, data prep and model build take 0.8–1.4 s, and result extraction about 0.2 s. "RAM" is peak RSS.
- **Model size:** h1 is 6.2k rows by 3.8k columns, h4 is 23.9k by 14.3k, and h8 is 47.6k by 28.4k (almost all binary).

HiGHS's own time / wall time / peak RAM. "Default" is upstream's thread setting; "threads=2" sets HiGHS `threads=2` and leaves upstream otherwise unchanged:

| Horizon, gap | 2 vCPU default | 2 vCPU threads=2 | 1 vCPU default | 1 vCPU threads=2 | Mac M-series, 10 cores (reference) |
|---|---|---|---|---|---|
| 1 GW, 0 | 0.14 s / 1.1 s / 149 MB | 0.08 / 1.2 / 147 | 0.23 / 1.4 / 152 | 0.08 / 1.1 / 147 | 0.07 / 2.4 / 173 |
| 1 GW, 0.5% | 0.10 / 1.2 / 147 | 0.08 / 1.1 / 146 | 0.20 / 1.3 / 149 | 0.10 / 1.3 / 148 | 0.07 / 2.5 / 172 |
| 4 GW, 0 | 0.73 / 2.0 / 214 | 0.65 / 1.9 / 211 | 1.12 / 2.6 / 220 | 0.97 / 2.4 / 215 | 0.66 / 3.4 / 246 |
| 4 GW, 0.5% | 0.63 / 1.9 / 213 | 0.69 / 2.0 / 212 | 1.02 / 2.5 / 220 | 0.89 / 2.3 / 213 | 0.60 / 3.2 / 244 |
| 8 GW, 0 | 9.8 / 11.3 / 396 | 10.3 / 12.0 / 387 | 16.3 / 18.0 / 400 | 12.1 / 13.6 / 384 | 8.2 / 11.2 / 404 |
| 8 GW, 0.5% | 8.9 / 10.4 / 390 | 9.4 / 11.0 / 385 | 7.4 / 9.1 / 391 | 11.6 / 13.1 / 389 | 3.5 / 6.6 / 386 |
| *extra:* 4 GW, 0.5%, all 4 chips free | 46 / 48 / 662 | 48 / 49 / 419 | 76 / 78 / 1,346 | 47 / 48 / 427 | 56 / 59 / 779 |
| *extra:* 8 GW, 0.5%, all 4 chips free | **killed for running out of memory** at 2 GB after 246 s | killed for memory after 629 s | killed for memory after 279 s | killed for memory after 766 s | hit the 600 s limit at a 3.1% gap, 2.6 GB |

Every run without chips ended at `Optimal` within the gap tolerance, on the root node (1 node).

**What the numbers say**

- **Without chips, an 8-GW horizon is cheap:** at most about 18 s and 400 MB on 1 vCPU. **1 vCPU is enough**, since 2 vCPU saves only about 20% at 8 GW.
- **HiGHS oversubscribes the container.** Inside Railway it sees all 48 host cores, and the cgroup quota doesn't hide them, so upstream's defaults start 24 threads and 41 workers on 1 or 2 vCPU. That costs time on 1 vCPU (8 GW at gap 0 takes 16.3 s versus 12.1 s) and memory with chips (1.35 GB versus 0.43 GB). Our solver must set `threads` to the container's vCPU count.
- **Gap 0 versus 0.5% hardly matters** on this input. 0.5% mainly caps the bad cases.
- **Joint all-chip planning over 8 GW is out of reach** with this formulation on any box we'd run: it runs out of memory at 2 GB, and even a 10-core Mac can't close it in 10 minutes. Over 4 GW it takes about 48 s and 0.43 GB with threads capped.
- **Caveats:** the xP input is synthetic, with the same shape every Gameweek, and only one squad was tested. A real model's projections may solve more slowly. Re-time the solver on our own xP in the CI regression test from [ADR 0002](../../../docs/adr/0002-own-solver-on-highs.md).

### Recommended solver budget

| Solve | Horizon | `mip_rel_gap` | `time_limit` | Other |
|---|---|---|---|---|
| Transfer plan, chips off or fixed to a Gameweek | Default is the xP model's stored 5 GW, per [Expected-points model design](20-xp-model-design.md). Allow up to 8. | 0.005 | 60 s, about 4× the worst case measured | HiGHS `threads` = vCPUs (1). One solve at a time, in a subprocess. Report the gap reached if the limit hits. |
| Joint chip solve (chip variables free) | At most 4 GW | 0.005 | 120 s | Same as above. Budget about 0.5 GB of solver RAM. |
| Chip timing over 6–8 GW | Enumerate candidate chip Gameweeks as forced-chip scenarios. Each costs about the same as a solve without chips (10–15 s). | 0.005 | 60 s each | Off-peak job. About 10 scenarios is about 2–3 min. |

- **Capacity:** for 10 Members, one transfer plan each per Gameweek is about 2–3 CPU-minutes.
- **Railway limit:** a 1 vCPU / 1 GB cap on the bot service fits the solver subprocess alongside the long-lived process, as long as threads are capped.

### Railway notes for the pipeline and operations tickets

- **Defaults:** new services default to US West (`sfo`). Region, resource limits and the Dockerfile builder had to be set through GraphQL (`serviceInstanceUpdate`, `serviceInstanceLimitsUpdate` via `railway api`), because `railway environment edit` reported "No changes to apply" (CLI 5.75).
- **Variable changes:** `railway variable delete` didn't trigger a redeploy.
- **CLI auto-update:** an auto-update once left the CLI without its binary until it was reinstalled. Pin the CLI version in CI.

### Probe removed

- **Project:** deletion of `fpl-probe-18-throwaway` was accepted on 21 Nov 16:08 UTC. Railway marks it deleted and purges it on 23 Nov, after its 48-hour grace period.
- **Deployments:** all 5 show `REMOVED`, so nothing is running and nothing is billing.
- **The owner's other project was never touched.**
