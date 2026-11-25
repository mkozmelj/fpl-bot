"""Completion rows: which idempotent job has finished for which period (spec, Sources and
ingestion: "each writing a completion row per Gameweek (elite, picks, gw_final, plus
price_archive per night)").

A period is a Gameweek (``gameweek_period(11)`` -> ``"gw11"``) or a night
(``night_period(date)`` -> ``"2026-11-23"``). Planners read these to decide what is missing (the
startup catch-up), and jobs check them so a re-run of a finished period does nothing.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.store.schema import JobCompletion


def gameweek_period(gameweek: int) -> str:
    return f"gw{gameweek}"


def night_period(night: date) -> str:
    return night.isoformat()


@dataclass(frozen=True)
class Completion:
    period: str
    completed_at: datetime


class CompletionStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def done(self, job: str, season: str, period: str) -> bool:
        return period in await self.done_periods(job, season, [period])

    async def done_periods(self, job: str, season: str, periods: Iterable[str]) -> set[str]:
        """Which of ``periods`` have a completion row for ``job``."""
        wanted = list(periods)
        if not wanted:
            return set()
        async with self._sessions() as session:
            rows = await session.scalars(
                select(JobCompletion.period).where(
                    JobCompletion.season == season,
                    JobCompletion.job == job,
                    JobCompletion.period.in_(wanted),
                )
            )
            return set(rows)

    async def record(self, job: str, season: str, period: str, at: datetime) -> None:
        """Mark ``job`` finished for ``period`` (a second call keeps the first time)."""
        async with self._sessions.begin() as session:
            await session.execute(
                insert(JobCompletion)
                .values(season=season, job=job, period=period, completed_at=at)
                .on_conflict_do_nothing()
            )

    async def latest(self, jobs: Iterable[str]) -> dict[str, Completion]:
        """The completion of the latest period of each of ``jobs`` that has one (``/status``):
        latest season, then latest Gameweek or night, whatever order they were completed in
        (the startup catch-up may finish GW9 after GW10)."""
        wanted = list(jobs)
        async with self._sessions() as session:
            rows = await session.execute(
                select(
                    JobCompletion.job,
                    JobCompletion.season,
                    JobCompletion.period,
                    JobCompletion.completed_at,
                ).where(JobCompletion.job.in_(wanted))
            )
            ranked: dict[str, tuple[tuple[str, int, str], Completion]] = {}
            for job, season, period, completed_at in rows:
                # "gw9" < "gw10" by length first; nights are ISO dates of one length.
                rank = (season, len(period), period)
                if job not in ranked or rank > ranked[job][0]:
                    ranked[job] = (rank, Completion(period, completed_at))
            return {job: completion for job, (_, completion) in ranked.items()}
