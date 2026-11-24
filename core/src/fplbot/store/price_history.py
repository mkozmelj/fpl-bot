"""Price history kept across seasons (ticket 37): evening price snapshots, actual Price changes
(an archived night also gets a ``price_archive`` completion row), the projection codes at
Price-alert time, and the news/status log. None of it is Member data (no CASCADE; ``/leave``
leaves it). Every write is idempotent, so a re-run job changes nothing.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.sources.price_history import FplNews, FplPriceChange, FplPriceSnapshot
from fplbot.store.schema import (
    FootballerNews,
    PriceChange,
    PricePrediction,
    PriceSnapshot,
)

# The completion-row job of the nightly archive (``store/completions.py``); periods are nights.
PRICE_ARCHIVE = "price_archive"


class Horizon(StrEnum):
    TONIGHT = "tonight"
    TOMORROW = "tomorrow"


@dataclass(frozen=True)
class Outcome:
    """``count`` predictions of ``code`` for the price update after ``night`` whose actual move
    was ``moved`` (+1 rose, -1 fell, 0 no change)."""

    night: date
    horizon: Horizon
    code: int
    moved: int
    count: int


class PriceHistoryStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def save_snapshot(
        self, season: str, taken_at: datetime, footballers: Iterable[FplPriceSnapshot]
    ) -> None:
        values = [
            {
                "season": season,
                "taken_at": taken_at,
                "footballer_id": f.footballer_id,
                "price": f.price,
                "percent": f.percent,
                "hourly_rate": f.hourly_rate,
                "likelihood_tonight": f.likelihoods[0],
                "likelihood_tomorrow": f.likelihoods[1],
                "likelihood_after": f.likelihoods[2],
                "locked_until": f.locked_until,
                "calibrating": f.calibrating,
            }
            for f in footballers
        ]
        if values:
            async with self._sessions.begin() as session:
                await session.execute(insert(PriceSnapshot).values(values).on_conflict_do_nothing())

    async def log_news(self, season: str, observed_at: datetime, states: Iterable[FplNews]) -> int:
        """Log each Footballer whose status or news differs from his latest logged row; the
        number of rows written."""
        async with self._sessions.begin() as session:
            latest = await session.execute(
                select(FootballerNews.footballer_id, FootballerNews.status, FootballerNews.news)
                .where(FootballerNews.season == season)
                .distinct(FootballerNews.footballer_id)
                .order_by(FootballerNews.footballer_id, FootballerNews.observed_at.desc())
            )
            known = {row.footballer_id: (row.status, row.news) for row in latest}
            changed = [
                {
                    "season": season,
                    "footballer_id": s.footballer_id,
                    "observed_at": observed_at,
                    "status": s.status,
                    "news": s.news,
                }
                for s in states
                if known.get(s.footballer_id) != (s.status, s.news)
            ]
            if changed:
                await session.execute(insert(FootballerNews).values(changed))
            return len(changed)

    async def save_changes(self, season: str, changes: Iterable[FplPriceChange]) -> int:
        """Store the Price changes not stored yet; the number of new ones."""
        values = [
            {
                "season": season,
                "footballer_id": c.footballer_id,
                "changed_at": c.changed_at,
                "night": c.night,
                "gameweek": c.gameweek,
                "club_id": c.club_id,
                "cost_before": c.cost_before,
                "cost_after": c.cost_after,
            }
            for c in changes
        ]
        if not values:
            return 0
        async with self._sessions.begin() as session:
            result = await session.execute(
                insert(PriceChange)
                .values(values)
                .on_conflict_do_nothing()
                .returning(PriceChange.footballer_id)
            )
            return len(result.all())

    async def save_predictions(
        self,
        season: str,
        night: date,
        made_at: datetime,
        codes: Iterable[tuple[int, int | None, int | None]],
    ) -> None:
        """Keep (Footballer id, tonight's code, tomorrow's code) for ``night`` unless that night
        already has the Footballer's codes (the first Price-alert time of a night counts)."""
        values = [
            {
                "season": season,
                "night": night,
                "footballer_id": footballer,
                "made_at": made_at,
                "tonight": tonight,
                "tomorrow": tomorrow,
            }
            for footballer, tonight, tomorrow in codes
            if tonight is not None or tomorrow is not None
        ]
        if values:
            async with self._sessions.begin() as session:
                await session.execute(
                    insert(PricePrediction).values(values).on_conflict_do_nothing()
                )

    async def outcomes(self, season: str) -> list[Outcome]:
        """Every scored prediction of ``season``, counted by target night, horizon, code and
        actual move. Only nights with a ``price_archive`` completion row are scored (there, a
        Footballer without a stored change did not change)."""
        async with self._sessions() as session:
            rows = await session.execute(_OUTCOMES, {"season": season, "job": PRICE_ARCHIVE})
            return [
                Outcome(
                    night=row.night,
                    horizon=Horizon.TONIGHT if row.days == 0 else Horizon.TOMORROW,
                    code=row.code,
                    moved=row.moved,
                    count=row.predictions,
                )
                for row in rows
            ]


_OUTCOMES = text("""
    SELECT p.night + h.days AS night, h.days AS days, h.code AS code,
           COALESCE(SIGN(c.cost_after - c.cost_before), 0)::int AS moved,
           COUNT(*)::int AS predictions
    FROM price_predictions p
    CROSS JOIN LATERAL (VALUES (0, p.tonight), (1, p.tomorrow)) AS h(days, code)
    JOIN job_completions a
      ON a.season = p.season AND a.job = :job
     AND a.period = to_char(p.night + h.days, 'YYYY-MM-DD')
    LEFT JOIN price_changes c
      ON c.season = p.season AND c.night = p.night + h.days AND c.footballer_id = p.footballer_id
    WHERE p.season = :season AND h.code IS NOT NULL
    GROUP BY 1, 2, 3, 4
""")
