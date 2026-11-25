"""Price and news history jobs (ticket 37). Each UK night (``planned_runs(night)``):

- "news-log": hourly ``bootstrap-static`` reads 08:00-23:00 UK; a Footballer's status or news
  is logged only when it changed;
- "price-snapshot" at 18:00, 20:00, 22:00, 23:00 and 23:45 UK: a compact row per Footballer
  (price, percent, hourly rate, the 3 likelihoods, lock flags), plus the news log (these hours
  take the place of that hour's news read). A missed snapshot is skipped, never back-filled
  (short scheduler grace); a re-run of one stores nothing new;
- "price-refresh" at 00:05 UK: a fresh ``bootstrap-static`` just after the price update, which
  refreshes reference data (new prices) and the news log;
- "price-archive" at 00:10 UK: ``stats/price-changes/`` stored as Price changes, then the
  night's ``price_archive`` completion row. With that row a re-run does nothing (no request).
  A missed archive is caught up later the same day (the endpoint is a rolling window).

All run at routine priority. Projection codes at Price-alert time are stored by the Price alert
job itself (``jobs/price_alert.py``).
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from fplbot.clock import UK_ZONE, Clock
from fplbot.jobs.runner import Job, waiting_while_updating
from fplbot.jobs.scheduler import PlannedRun
from fplbot.sources.fpl import FplSource, FplUnexpectedStatus, Priority
from fplbot.sources.price_history import news_states, price_changes, price_snapshot
from fplbot.store.completions import CompletionStore, night_period
from fplbot.store.price_history import PRICE_ARCHIVE, PriceHistoryStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)

NEWS_JOB = "news-log"
SNAPSHOT_JOB = "price-snapshot"
REFRESH_JOB = "price-refresh"
ARCHIVE_JOB = "price-archive"

NEWS_HOURS = range(8, 24)  # 08:00 to 23:00 UK
SNAPSHOT_TIMES = (time(18), time(20), time(22), time(23), time(23, 45))
REFRESH_AT = time(0, 5)  # the morning after the night
ARCHIVE_AT = time(0, 10)
PRICE_CHANGES_PATH = "stats/price-changes/"

# A snapshot this late is skipped (never back-filled); an archive is caught up all day.
SNAPSHOT_GRACE = timedelta(minutes=5)
REFRESH_GRACE = timedelta(hours=1)
ARCHIVE_GRACE = timedelta(hours=23)
# Reads reuse a bootstrap-static fetched this recently (e.g. by a Price alert at the same time).
SNAPSHOT_REUSE = timedelta(minutes=2)
NEWS_REUSE = timedelta(minutes=5)


class PriceArchive:
    def __init__(
        self,
        *,
        history: PriceHistoryStore,
        completions: CompletionStore,
        reference: ReferenceStore,
        clock: Clock,
    ) -> None:
        self._history = history
        self._completions = completions
        self._reference = reference
        self._clock = clock

    async def plan(self, now: datetime) -> list[PlannedRun]:
        """Planner (``Scheduler.add``): last night's runs still to come or catch up (00:05,
        00:10) and today's."""
        today = now.astimezone(UK_ZONE).date()
        runs = [
            *await self.planned_runs(today - timedelta(days=1)),
            *await self.planned_runs(today),
        ]
        # Runs already past their grace are left out (rather than logged as skipped on every
        # startup): a missed snapshot or news read is simply not taken.
        return [run for run in runs if run.at + run.grace >= now]

    async def planned_runs(self, night: date) -> list[PlannedRun]:
        """The runs for UK night ``night``, earliest first."""
        snapshot_at = {datetime.combine(night, t, UK_ZONE) for t in SNAPSHOT_TIMES}
        news_at = {
            datetime.combine(night, time(hour), UK_ZONE) for hour in NEWS_HOURS
        } - snapshot_at
        morning = night + timedelta(days=1)
        runs = [
            *(PlannedRun(at, NEWS_JOB, self.news_job(), Priority.ROUTINE) for at in news_at),
            *(
                PlannedRun(at, SNAPSHOT_JOB, self.snapshot_job(at), grace=SNAPSHOT_GRACE)
                for at in snapshot_at
            ),
            PlannedRun(
                datetime.combine(morning, REFRESH_AT, UK_ZONE),
                REFRESH_JOB,
                self.refresh_job(),
                grace=REFRESH_GRACE,
            ),
            PlannedRun(
                datetime.combine(morning, ARCHIVE_AT, UK_ZONE),
                ARCHIVE_JOB,
                self.archive_job(night),
                grace=ARCHIVE_GRACE,
            ),
        ]
        return sorted(runs, key=lambda run: run.at)

    def news_job(self) -> Job:
        async def job(fpl: FplSource) -> None:
            await self._log_news(await fpl.bootstrap_static(NEWS_REUSE))

        return job

    def snapshot_job(self, at: datetime) -> Job:
        """The snapshot planned for ``at`` (its rows are stamped ``at``, so a re-run stores
        nothing new)."""

        async def job(fpl: FplSource) -> None:
            bootstrap = await fpl.bootstrap_static(SNAPSHOT_REUSE)
            await self._history.save_snapshot(season_of(at), at, price_snapshot(bootstrap))
            await self._log_news(bootstrap)
            log.info("price snapshot stored")

        return job

    def refresh_job(self) -> Job:
        async def job(fpl: FplSource) -> None:
            await self._reference.refresh(fpl, max_age=timedelta(0))
            await self._log_news(await fpl.bootstrap_static())  # the copy just fetched

        return waiting_while_updating(job, self._clock)

    def archive_job(self, night: date) -> Job:
        """Archive the Price changes of UK night ``night`` (once)."""

        async def job(fpl: FplSource) -> None:
            season = season_of(self._clock.now())
            period = night_period(night)
            if await self._completions.done(PRICE_ARCHIVE, season, period):
                log.info("price archive for %s already stored", period)
                return
            data = await fpl.get_json(PRICE_CHANGES_PATH)
            if data is None:
                raise FplUnexpectedStatus(404)
            stored = await self._history.save_changes(season, price_changes(data))
            await self._completions.record(PRICE_ARCHIVE, season, period, self._clock.now())
            log.info("price archive for %s stored: %d new price changes", period, stored)

        return waiting_while_updating(job, self._clock)

    async def _log_news(self, bootstrap: dict[str, Any]) -> None:
        now = self._clock.now()
        logged = await self._history.log_news(season_of(now), now, news_states(bootstrap))
        if logged:
            log.info("news log: %d changes", logged)
