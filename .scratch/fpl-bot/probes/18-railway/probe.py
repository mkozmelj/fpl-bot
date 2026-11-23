"""Throwaway Railway probe for ticket 18 (Probe Railway: FPL reachability and solver timing).

MODE=reach  Sample public FPL endpoints from Railway's shared egress for >=24 h.
MODE=bench  Time upstream open-fpl-solver on highspy for a horizon x gap matrix.

Standard library only (the solver runs in its own venv as a subprocess).
Politeness rules: generic browser User-Agent, no personal details anywhere,
>= 1.5 s between FPL requests, never retry a 403, honour Retry-After on 429.
"""

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

FPL = "https://fantasy.premierleague.com/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9"}
MIN_SPACING_S = 1.5
OVERALL_LEAGUE = 314  # FPL's public "Overall" classic league
SOLVER_DIR = Path(os.environ.get("SOLVER_DIR", "/opt/open-fpl-solver"))
SOLVER_PY = Path(os.environ.get("SOLVER_PY", SOLVER_DIR / ".venv/bin/python"))

_last_request = 0.0


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def emit(tag: str, obj: dict) -> None:
    print(f"{tag} {json.dumps(obj, separators=(',', ':'))}", flush=True)


def fetch(url: str, timeout: float = 30) -> tuple[int, bytes, dict, float]:
    """One polite GET. Returns (status, body, selected headers, latency_ms). Never retries."""
    global _last_request
    wait = MIN_SPACING_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    req = urllib.request.Request(url, headers=HEADERS)
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body, status, hdrs = r.read(), r.status, r.headers
    except urllib.error.HTTPError as e:
        body, status, hdrs = e.read(), e.code, e.headers
    except Exception as e:  # network error, timeout
        return -1, repr(e).encode(), {}, (time.monotonic() - t0) * 1000
    keep = {k.lower(): v for k, v in hdrs.items() if k.lower() in {"retry-after", "cf-cache-status", "x-cache", "age", "server", "via", "content-type"}}
    return status, body, keep, (time.monotonic() - t0) * 1000


def fetch_json(url: str) -> dict | list:
    status, body, _, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"{url} -> {status}")
    return json.loads(body)


def env_info() -> dict:
    info = {"python": sys.version.split()[0], "platform": platform.platform(), "cpu_count": os.cpu_count()}
    if hasattr(os, "sched_getaffinity"):
        info["affinity"] = len(os.sched_getaffinity(0))
    for f in ("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/memory.max"):
        try:
            info[f.rsplit("/", 1)[1]] = Path(f).read_text().strip()
        except OSError:
            pass
    info["railway_region"] = os.environ.get("RAILWAY_REPLICA_REGION")
    return info


# ---------------------------------------------------------------- reach


def egress_ip() -> str | None:
    try:
        with urllib.request.urlopen(urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": UA}), timeout=10) as r:
            return json.loads(r.read())["ip"]
    except Exception:
        return None


def reach() -> None:
    interval = int(os.environ.get("ROUND_INTERVAL_S", "600"))
    backoff_rounds = 3  # after a 403 on an endpoint, skip it for this many rounds (no retry)
    emit("REACH_START", {"ts": now(), "env": env_info(), "interval_s": interval, "ua": UA})
    gw, entry = None, None
    counts: dict[str, dict[str, int]] = {}
    blocks: list[dict] = []
    skip_until: dict[str, int] = {}
    ips: dict[str, int] = {}
    start = time.time()
    rnd = 0
    last_ip_check = 0.0
    while True:
        rnd += 1
        round_start = time.monotonic()
        if time.time() - last_ip_check > 3600:
            ip = egress_ip()
            last_ip_check = time.time()
            if ip:
                ips[ip] = ips.get(ip, 0) + 1
                emit("REACH_IP", {"ts": now(), "ip": ip})
        plan = [("bootstrap-static", f"{FPL}/bootstrap-static/"), ("fixtures", f"{FPL}/fixtures/")]
        if gw:
            plan.append(("event-live", f"{FPL}/event/{gw}/live/"))
        plan.append(("league-standings", f"{FPL}/leagues-classic/{OVERALL_LEAGUE}/standings/"))
        rate_limited = False
        for name, url in plan + [("entry-picks", None)]:
            if name == "entry-picks":
                if not (gw and entry):
                    continue
                url = f"{FPL}/entry/{entry}/event/{gw}/picks/"
            if rate_limited or skip_until.get(name, 0) >= rnd:
                counts.setdefault(name, {}).setdefault("skipped", 0)
                counts[name]["skipped"] += 1
                continue
            status, body, hdrs, ms = fetch(url)
            counts.setdefault(name, {}).setdefault(str(status), 0)
            counts[name][str(status)] += 1
            rec = {"ts": now(), "round": rnd, "ep": name, "status": status, "bytes": len(body), "ms": round(ms), **hdrs}
            if status != 200:
                rec["body_head"] = body[:200].decode("utf-8", "replace")
                blocks.append({"ts": rec["ts"], "ep": name, "status": status})
                if status == 403:
                    skip_until[name] = rnd + backoff_rounds
                if status == 429:
                    rate_limited = True
                    ra = hdrs.get("retry-after")
                    if ra and ra.isdigit():
                        time.sleep(min(int(ra), 3600))
            emit("REACH", rec)
            if status == 200:
                try:
                    data = json.loads(body)
                    if name == "bootstrap-static":
                        cur = [e["id"] for e in data["events"] if e.get("is_current")]
                        gw = cur[0] if cur else gw
                    elif name == "league-standings":
                        entry = data["standings"]["results"][0]["entry"]
                except Exception as e:
                    emit("REACH_PARSE_ERR", {"ts": now(), "ep": name, "err": repr(e)})
        emit(
            "REACH_SUMMARY",
            {"ts": now(), "round": rnd, "hours": round((time.time() - start) / 3600, 2), "gw": gw, "counts": counts, "non200": blocks[-50:], "n_non200": len(blocks), "ips": ips},
        )
        time.sleep(max(0, interval - (time.monotonic() - round_start)))


# ---------------------------------------------------------------- bench


def build_inputs(work: Path) -> tuple[dict, int]:
    """Fetch FPL data once, seed upstream's HTTP cache so it never fetches, write a review-format xP CSV
    from ep_next scaled by fixture difficulty, and return a team JSON (Overall rank-1's public picks)."""
    static = fetch_json(f"{FPL}/bootstrap-static/")
    fixtures = fetch_json(f"{FPL}/fixtures/")
    league = fetch_json(f"{FPL}/leagues-classic/{OVERALL_LEAGUE}/standings/")
    cur = next(e["id"] for e in static["events"] if e["is_current"])
    nxt = next(e["id"] for e in static["events"] if e["is_next"])
    entry = league["standings"]["results"][0]["entry"]
    picks = fetch_json(f"{FPL}/entry/{entry}/event/{cur}/picks/")

    cache_dir = SOLVER_DIR / ".cache"
    cache_dir.mkdir(exist_ok=True)
    far = time.time() + 10 * 365 * 86400  # upstream treats cache entries newer than 300 s as fresh
    (cache_dir / "http_cache.json").write_text(
        json.dumps({f"{FPL}/bootstrap-static/": {"data": static, "timestamp": far}, f"{FPL}/fixtures/": {"data": fixtures, "timestamp": far}})
    )

    pos = {t["id"]: t["singular_name_short"][0] for t in static["element_types"]}
    teams = {t["id"]: t["name"] for t in static["teams"]}
    fx: dict[tuple[int, int], list[int]] = {}
    for f in fixtures:
        if f["event"]:
            fx.setdefault((f["team_h"], f["event"]), []).append(f["team_h_difficulty"])
            fx.setdefault((f["team_a"], f["event"]), []).append(f["team_a_difficulty"])
    gws = list(range(nxt, min(39, nxt + 8)))
    lines = ["ID,Name,Pos,Value,Team," + ",".join(f"{w}_xMins,{w}_Pts" for w in gws)]
    for el in static["elements"]:
        ep = float(el.get("ep_next") or 0)
        chance = el.get("chance_of_playing_next_round")
        avail = 1.0 if chance is None else chance / 100
        base_min = 90 * avail if el["minutes"] > 0 else 0
        cols = []
        for w in gws:
            diffs = fx.get((el["team"], w), [])
            pts = sum(ep * (1.25 - 0.125 * (d - 1)) for d in diffs)
            cols += [f"{base_min * len(diffs):.0f}", f"{pts:.3f}"]
        name = el["web_name"].replace(",", " ")
        lines.append(f"{el['id']},{name},{pos[el['element_type']]},{el['now_cost'] / 10},{teams[el['team']]}," + ",".join(cols))
    (SOLVER_DIR / "data" / "probe.csv").write_text("\n".join(lines) + "\n")

    cost = {el["id"]: el["now_cost"] for el in static["elements"]}
    team = {
        "picks": [
            {"element": p["element"], "position": p["position"], "selling_price": cost[p["element"]], "purchase_price": cost[p["element"]], "multiplier": 1, "is_captain": False, "is_vice_captain": False}
            for p in picks["picks"]
        ],
        "chips": [],
        "transfers": {"limit": 2, "made": 0, "bank": picks["entry_history"]["bank"], "value": picks["entry_history"]["value"], "cost": 4},
    }
    return team, nxt


SOLVE_REPORT = re.compile(r"^\s*(Status|Primal bound|Dual bound|Gap|P-D integral|Solution status|Timing|Max sub-MIP depth|Nodes|Repair LPs|LP iterations)\s+(.*)$")


def run_one(label: str, team: dict, horizon: int, gap: float, secs: int, chips: bool) -> dict:
    cfg = {
        "datasource": "probe",
        "team_data": "json_string",
        "team_json": json.dumps(team),
        "horizon": horizon,
        "gap": gap,
        "secs": secs,
        "xmin_lb": round(37.5 * horizon),  # upstream's 300 over 8 GW, scaled so short horizons keep a comparable pool
        "verbose": True,
        "print_squads": False,
        "print_result_table": True,
        "print_transfer_chip_summary": True,
        "export_image": False,
        "solutions_file": "",
    }
    if chips:
        cfg["chip_limits"] = {"bb": 1, "wc": 1, "fh": 1, "tc": 1}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
        cfg_path = f.name
    threads = os.environ.get("BENCH_THREADS")
    if threads:  # upstream unchanged; only HiGHS's `threads` option is set on every Highs instance
        wrap = (
            "import sys, runpy, highspy\n"
            "_o = highspy.Highs.__init__\n"
            f"def _i(self, *a, **k):\n    _o(self, *a, **k)\n    self.setOptionValue('threads', {int(threads)})\n"
            "highspy.Highs.__init__ = _i\n"
            f"sys.argv = ['solve.py', '--config', {cfg_path!r}]\n"
            "runpy.run_path('solve.py', run_name='__main__')\n"
        )
        cmd = [str(SOLVER_PY), "-u", "-c", wrap]
    else:
        cmd = [str(SOLVER_PY), "-u", "solve.py", "--config", cfg_path]
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=SOLVER_DIR / "run", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, t_mip, t_report = [], None, None
    for line in proc.stdout:
        lines.append(line)
        if t_mip is None and re.search(r"^MIP\b.* has \d+ rows", line):
            t_mip = time.monotonic() - t0
        if t_report is None and "Solving report" in line:
            t_report = time.monotonic() - t0
    out = "".join(lines)
    _, status, ru = os.wait4(proc.pid, 0)
    wall = time.monotonic() - t0
    maxrss = ru.ru_maxrss * (1 if sys.platform == "darwin" else 1024)  # bytes
    report = {}
    in_report = False
    for line in out.splitlines():
        if "Solving report" in line:
            in_report = True
            continue
        if in_report:
            m = SOLVE_REPORT.match(line)
            if m:
                report[m.group(1)] = m.group(2).strip()
    pool = re.search(r"Filtered player pool from (\d+) to (\d+)", out)
    size = re.search(r"MIP(?:\s+\S+)?\s+has (\d+) rows; (\d+) cols; (\d+) nonzeros; (\d+) integer", out)
    threads_m = re.search(r"Thread count[^\n]*", out)
    res = {
        "label": label,
        "horizon": horizon,
        "gap": gap,
        "chips": chips,
        "time_limit": secs,
        "exit": os.waitstatus_to_exitcode(status),
        "wall_s": round(wall, 2),
        "build_s": round(t_mip, 2) if t_mip else None,  # process start -> model handed to HiGHS (imports, data prep, model build)
        "post_s": round(wall - t_report, 2) if t_report else None,  # solving report -> exit (result extraction, printing)
        "highs_timing_s": report.get("Timing"),
        "highs_status": report.get("Status"),
        "highs_gap": report.get("Gap"),
        "nodes": report.get("Nodes"),
        "peak_rss_mb": round(maxrss / 2**20, 1),
        "pool": pool.groups() if pool else None,
        "mip_size": size.groups() if size else None,
        "threads_line": threads_m.group(0) if threads_m else None,
        "threads_opt": os.environ.get("BENCH_THREADS"),
    }
    if res["exit"] != 0 or not report:
        res["tail"] = out[-1500:]
    os.unlink(cfg_path)
    return res


def bench() -> None:
    label = os.environ.get("BENCH_LABEL", "unlabelled")
    secs = int(os.environ.get("BENCH_TIME_LIMIT_S", "900"))
    emit("BENCH_START", {"ts": now(), "label": label, "env": env_info(), "time_limit": secs})
    team, nxt = build_inputs(SOLVER_DIR)
    hv = subprocess.run([str(SOLVER_PY), "-c", "import importlib.metadata as m;print(m.version('highspy'))"], capture_output=True, text=True).stdout.strip()
    emit("BENCH_INPUTS", {"ts": now(), "next_gw": nxt, "highspy": hv, "bank": team["transfers"]["bank"], "n_picks": len(team["picks"])})
    matrix = [(h, g, False) for h in (1, 4, 8) for g in (0.0, 0.005)]
    matrix += [(4, 0.005, True), (8, 0.005, True)]
    if os.environ.get("BENCH_ONLY"):
        matrix = [m for m in matrix if f"{m[0]}:{m[1]}:{int(m[2])}" in os.environ["BENCH_ONLY"].split(",")]
    emit("BENCH_WARMUP", run_one(label + "-warmup", team, 1, 0.0, secs, False))  # cold start: bytecode compile, first imports
    results = []
    for h, g, c in matrix:
        r = run_one(label, team, h, g, secs, c)
        results.append(r)
        emit("BENCH", r)
    emit("BENCH_DONE", {"ts": now(), "label": label, "results": [{k: r[k] for k in ("horizon", "gap", "chips", "wall_s", "build_s", "post_s", "highs_timing_s", "highs_status", "highs_gap", "peak_rss_mb")} for r in results]})


if __name__ == "__main__":
    mode = os.environ.get("MODE", "reach")
    if mode == "reach":
        reach()
    elif mode == "bench":
        bench()
        if os.environ.get("BENCH_HOLD"):
            while True:  # keep the container up so Railway does not restart the bench
                time.sleep(3600)
    else:
        raise SystemExit(f"unknown MODE {mode}")
