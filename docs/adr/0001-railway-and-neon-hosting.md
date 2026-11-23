# Host on Railway Hobby with Neon Postgres, deployed only by CI

The bot runs as one always-on container on the owner's existing Railway Hobby plan (EU West, Amsterdam), with its data in Neon free Postgres (EU). Research had recommended Oracle Always Free, and that is the only truly zero-cost always-on option. We chose Railway anyway: the owner already pays for Hobby, its $5 included usage covers most of the roughly $2–5 a month this adds, and it has a far simpler operating model (no VM to patch, no idle-reclaim risk). The database stays on Neon rather than Railway Postgres so that it costs nothing while idle and the container stays stateless and portable.

## Consequences

- Deploys happen only from GitHub Actions. CI builds one image, tests and scans that exact image, and publishes it to GHCR (public, because the repo is). It then runs `railway redeploy` with a project token scoped to the production environment, which can only deploy and read logs, and smoke-checks the result with automatic rollback. Railway's GitHub autodeploy and "wait for CI" were rejected because they need broader GitHub App permissions and let skipped workflows through. The Railway MCP is for development and observability only.
- RAM is the main cost, so CPU-heavy work (solver, xP fits) runs in short-lived subprocesses and the long-lived process stays small.
- Railway's outbound IPs are shared datacenter addresses, and its health checks are HTTP-only and run at deploy time, so they don't monitor a worker. FPL reachability is probed before relying on it, and liveness monitoring is an Operations concern.
- The fallback is to run the same container on Oracle Always Free or a GCP e2-micro (see the hosting research), pointed at the same Neon database.
