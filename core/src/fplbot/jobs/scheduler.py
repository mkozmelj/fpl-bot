"""The scheduler: runs each feature's planned jobs on time, with nothing persisted.

Features plug in a *planner*: an async function that, given "now", reads the DB and the stored
FPL deadlines and returns the runs it wants (``PlannedRun``). The scheduler asks every planner
for a fresh plan at startup, after every job it fired has finished, when ``rebuild()`` is called
(e.g. after a settings change) and at least every ``REPLAN_EVERY``. So the plan always follows the
data, and a restart loses nothing a planner can derive again (spec: "no persisted job store").

A run fires when it is due (``at <= now``) and not more than its ``grace`` late (misfire grace
window); later than that it is skipped. Each run has a ``key``; a key fires at most once per
process, so a planner may keep returning a run it already fired. That memory is not kept across
restarts: a run still inside its grace window after a restart fires again, so a job that must not
repeat (one that sends messages) checks its own completion row (``store/completions.py``).

All waiting is ``clock.sleep``, so the test harness runs the schedule in simulated time.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fplbot.clock import Clock
from fplbot.jobs.runner import Job, JobRunner
from fplbot.sources.fpl import Priority

log = logging.getLogger(__name__)

DEFAULT_GRACE = timedelta(minutes=10)
REPLAN_EVERY = timedelta(hours=1)
# Fired keys are forgotten after this long, so the memory stays small.
FORGET_FIRED_AFTER = timedelta(days=7)


@dataclass(frozen=True)
class PlannedRun:
    at: datetime  # when the run is due (timezone-aware)
    name: str  # the job name the owner sees in incident DMs, e.g. "picks"
    job: Job
    priority: Priority = Priority.ROUTINE
    # Identity across re-plans: a key fires at most once per process. Defaults to name@at.
    key: str = ""
    grace: timedelta = DEFAULT_GRACE
    run_key: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_key", self.key or f"{self.name}@{self.at.isoformat()}")


Planner = Callable[[datetime], Awaitable[Iterable[PlannedRun]]]


class Scheduler:
    def __init__(self, clock: Clock, jobs: JobRunner) -> None:
        self._clock = clock
        self._jobs = jobs
        self._planners: list[Planner] = []
        self._fired: dict[str, datetime] = {}
        self._loop: asyncio.Task[None] | None = None
        self._sleeping = False
        self._replan = False
        self._stopped = True

    def add(self, planner: Planner) -> None:
        """Register a feature's planner. Do it before ``start``."""
        self._planners.append(planner)

    def remove(self, planner: Planner) -> None:
        """Unregister a planner (before ``start``), e.g. a test leaving a feature out."""
        self._planners.remove(planner)

    @property
    def tasks(self) -> set[asyncio.Task[None]]:
        """The scheduler's own task while it runs (the test harness settles it)."""
        return {self._loop} if self._loop is not None and not self._loop.done() else set()

    def start(self) -> None:
        self._stopped = False
        self._restart()

    def rebuild(self) -> None:
        """Re-plan now, e.g. after data that planners read has changed."""
        if self._stopped:
            return
        if self._loop is None or self._loop.done() or self._sleeping:
            self._restart()
        else:
            self._replan = True  # planning right now: plan again before sleeping

    async def stop(self) -> None:
        self._stopped = True
        if self._loop is not None:
            self._loop.cancel()
            await asyncio.gather(self._loop, return_exceptions=True)
            self._loop = None

    def _restart(self) -> None:
        if self._loop is not None:
            self._loop.cancel()
        self._sleeping = False
        self._loop = asyncio.create_task(self._run(), name="scheduler")

    async def _run(self) -> None:
        while True:
            self._replan = False
            now = self._clock.now()
            runs = await self._plan(now)
            self._fire_due(runs, now)
            if self._replan:
                continue
            upcoming = [r.at for r in runs if r.at > now and r.run_key not in self._fired]
            wake = min([*upcoming, now + REPLAN_EVERY])
            self._sleeping = True
            try:
                await self._clock.sleep((wake - now).total_seconds())
            finally:
                self._sleeping = False

    async def _plan(self, now: datetime) -> list[PlannedRun]:
        runs: list[PlannedRun] = []
        for planner in self._planners:
            try:
                runs.extend(await planner(now))
            except Exception as error:
                log.error("planner %s failed: %s", _name(planner), type(error).__name__)
        return sorted(runs, key=lambda r: r.at)

    def _fire_due(self, runs: list[PlannedRun], now: datetime) -> None:
        for key, at in list(self._fired.items()):
            if now - at > FORGET_FIRED_AFTER:
                del self._fired[key]
        for run in runs:
            if run.at > now or run.run_key in self._fired:
                continue
            self._fired[run.run_key] = now
            if now - run.at > run.grace:
                log.info("job %s skipped: missed by more than its grace window", run.name)
                continue
            task = self._jobs.start(run.name, run.job, run.priority)
            task.add_done_callback(lambda _: self.rebuild())


def daily_occurrences(now: datetime, at: time, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The latest moment at or before ``now`` that was ``at`` local time in ``zone``, and the
    next one after ``now`` (DST-safe: each is built from its own local date)."""
    today = now.astimezone(zone).date()
    candidates = [
        datetime.combine(today + timedelta(days=offset), at, tzinfo=zone).astimezone(UTC)
        for offset in (-1, 0, 1)
    ]
    previous = max(c for c in candidates if c <= now)
    upcoming = min(c for c in candidates if c > now)
    return previous, upcoming


def daily(
    name: str,
    job: Job,
    at: time,
    zone: ZoneInfo,
    *,
    priority: Priority = Priority.ROUTINE,
    grace: timedelta = DEFAULT_GRACE,
) -> Planner:
    """A planner for a job that runs once a day at ``at`` local time in ``zone``."""

    async def plan(now: datetime) -> list[PlannedRun]:
        return [
            PlannedRun(at=moment, name=name, job=job, priority=priority, grace=grace)
            for moment in daily_occurrences(now, at, zone)
        ]

    plan.__qualname__ = f"daily {name}"
    return plan


def _name(planner: Planner) -> str:
    return getattr(planner, "__qualname__", type(planner).__name__)
