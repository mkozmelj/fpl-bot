"""The nightly Price alert job (tickets 15, 36).

Each Member's alert goes out at their alert time, clamped to 17:00-23:15 UK
(``advice.alert_time``). ``planned_runs(night)`` gives one run per distinct send time that night;
the run for a send time handles every Member sharing it with one fresh ``bootstrap-static``
fetch at Price-alert priority.

Silence: a Member with nothing to report gets nothing, as does everyone when FPL's projections
are calibrating. A failed fetch (FPL down, or no projection fields at all) is retried once after
10 minutes if that still lands by 23:15 UK (a 403 is never retried); if it still fails, Members
get nothing and the owner gets one DM for the night, however many send times fail. The job
reports its own failures, so the runner sees it succeed. Logs name Members by number only.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fplbot.advice.alert_time import UK, WINDOW_CLOSES, send_time_on_night, send_times_on_night
from fplbot.advice.price_alert import FootballerPrice, price_alert, squad_may_be_stale
from fplbot.clock import Clock
from fplbot.delivery import texts
from fplbot.delivery.owner_alerts import OwnerAlerts
from fplbot.delivery.price_alert import render_price_alert
from fplbot.jobs.runner import Job
from fplbot.sources.fpl import FplBlocked, FplError, FplGameweek, FplSource, Priority
from fplbot.sources.price_projections import price_projections
from fplbot.store.members import MemberRecord, MemberStore
from fplbot.store.seasons import season_of
from fplbot.store.squads import SquadStore
from fplbot.store.watch_list import WatchListStore

log = logging.getLogger(__name__)

JOB_NAME = "price-alert"
RETRY_AFTER = timedelta(minutes=10)

SendMessage = Callable[[int, str], Awaitable[None]]


@dataclass(frozen=True)
class PlannedRun:
    """A job to run at ``at`` (for the scheduler, ticket 31)."""

    at: datetime
    name: str
    job: Job
    priority: Priority


@dataclass(frozen=True)
class _Night:
    prices: dict[int, FootballerPrice]
    gameweeks: tuple[FplGameweek, ...]


class PriceAlerts:
    def __init__(
        self,
        *,
        members: MemberStore,
        watch_list: WatchListStore,
        squads: SquadStore,
        owner_alerts: OwnerAlerts,
        clock: Clock,
        send: SendMessage,
    ) -> None:
        self._members = members
        self._watch_list = watch_list
        self._squads = squads
        self._owner_alerts = owner_alerts
        self._clock = clock
        self._send = send

    async def planned_runs(self, night: date) -> list[PlannedRun]:
        """One run per distinct send time on UK night ``night``, earliest first."""
        settings = [
            (member.alert_time, ZoneInfo(member.timezone))
            for member in await self._members.active()
            if member.timezone
        ]
        return [
            PlannedRun(at, JOB_NAME, self.job(at), Priority.PRICE_ALERT)
            for at in send_times_on_night(settings, night)
        ]

    def job(self, send_time: datetime) -> Job:
        """The run for every Member whose alert goes out at ``send_time``."""
        night = send_time.astimezone(UK).date()

        async def job(fpl: FplSource) -> None:
            members = [m for m in await self._members.active() if _sends_at(m, send_time, night)]
            if not members:
                return
            try:
                data = await self._fetch(fpl, night)
            except FplError as error:
                log.warning("price alert data failed: %s", error.code)
                await self._owner_alerts.failed_once(
                    JOB_NAME, error.code, night, texts.price_alert_failed(error.code, JOB_NAME)
                )
                return
            if not any(p.tonight is not None for p in data.prices.values()):
                log.info("price projections unavailable (calibrating): no alerts")
                return
            for member in members:
                await self._alert(member, data, night)

        return job

    async def _fetch(self, fpl: FplSource, night: date) -> _Night:
        cutoff = datetime.combine(night, WINDOW_CLOSES, UK)
        try:
            return await _night_data(fpl)
        except FplBlocked:
            raise
        except FplError as error:
            if self._clock.now() + RETRY_AFTER > cutoff:
                raise
            log.info("price alert data failed (%s), retrying in 10 minutes", error.code)
        await self._clock.sleep(RETRY_AFTER.total_seconds())
        return await _night_data(fpl)

    async def _alert(self, member: MemberRecord, data: _Night, night: date) -> None:
        now = self._clock.now()
        season = season_of(now)
        passed = [g for g in data.gameweeks if g.deadline <= now]
        upcoming = [g for g in data.gameweeks if g.deadline > now]
        last = passed[-1] if passed else None
        following = upcoming[0] if upcoming else None
        gameweek = following or last  # the Gameweek Members are making transfers for
        if gameweek is None:
            return
        squad = await self._squads.latest_squad(member.number, season, last.id) if last else None
        owned = [p.footballer_id for p in (*squad.xi, *squad.bench)] if squad else []
        alert = price_alert(
            gameweek=gameweek.id,
            owned=owned,
            watched=await self._watch_list.footballer_ids(member.chat_id, now),
            prices=data.prices,
            squad_may_be_stale=squad_may_be_stale(
                squad_gameweek=squad.gameweek if squad else None,
                last_gameweek=last.id if last else None,
                next_deadline=following.deadline if following else None,
                price_update=datetime.combine(night + timedelta(days=1), time(0), UK),
            ),
        )
        if alert is None:
            return
        try:
            await self._send(member.chat_id, render_price_alert(alert))
        except Exception as error:  # one Member's chat failing must not stop the others
            log.warning(
                "member %d price alert not delivered: %s", member.number, type(error).__name__
            )
            return
        log.info("member %d price alert sent", member.number)


async def _night_data(fpl: FplSource) -> _Night:
    """A fresh ``bootstrap-static`` (one request), read for prices and Gameweeks."""
    bootstrap = await fpl.bootstrap_static(timedelta(0))
    reference = await fpl.reference()  # the copy just fetched, no second request
    return _Night(price_projections(bootstrap), reference.gameweeks)


def _sends_at(member: MemberRecord, send_time: datetime, night: date) -> bool:
    if not member.timezone:
        return False
    return send_time_on_night(member.alert_time, ZoneInfo(member.timezone), night).at == send_time
