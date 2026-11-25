"""Elite ownership (ticket 34): per Gameweek, cohort and Footballer, aggregates only.

Written once per Gameweek by the Elite sampler (``jobs/elite.py``) and read by ``/gap``. Never
holds a sampled manager's ID or Squad. Kept across seasons (spec: "Elite ownership results");
Footballer ids are season-scoped, so every read is per ``season``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.store.schema import EliteChip, EliteOwnership, EliteSample


@dataclass(frozen=True)
class FootballerShares:
    """Shares of the sample, 0 to 1; ``eo`` is the mean multiplier."""

    ownership: float
    xi: float
    captain: float
    eo: float


@dataclass(frozen=True)
class EliteFigures:
    cohort: str  # "10k"
    gameweek: int
    cohort_size: int
    target_size: int
    sample_size: int
    margin_of_error: float  # as a share: 0.02 is ±2%
    footballers: Mapping[int, FootballerShares]
    chips: Mapping[str, float]  # FPL chip name -> share of the sample that played it
    partial: bool = False  # the sampler stopped before its target (ticket 35)
    read_late: bool = False  # the cohort's standings were read after the first kickoff


class EliteStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def save(self, season: str, figures: EliteFigures, at: datetime) -> None:
        """Store (or replace) one cohort's figures for a Gameweek, in one transaction."""
        key = {"season": season, "gameweek": figures.gameweek, "cohort": figures.cohort}
        async with self._sessions.begin() as session:
            await session.execute(
                delete(EliteSample).where(
                    EliteSample.season == season,
                    EliteSample.gameweek == figures.gameweek,
                    EliteSample.cohort == figures.cohort,
                )
            )
            session.add(
                EliteSample(
                    **key,
                    cohort_size=figures.cohort_size,
                    target_size=figures.target_size,
                    sample_size=figures.sample_size,
                    margin_of_error=figures.margin_of_error,
                    sampled_at=at,
                    partial=figures.partial,
                    read_late=figures.read_late,
                )
            )
            await session.flush()
            session.add_all(
                EliteOwnership(
                    **key,
                    footballer_id=footballer,
                    ownership=shares.ownership,
                    xi_share=shares.xi,
                    captain_share=shares.captain,
                    eo=shares.eo,
                )
                for footballer, shares in figures.footballers.items()
            )
            session.add_all(
                EliteChip(**key, chip=chip, share=share) for chip, share in figures.chips.items()
            )

    async def figures(self, season: str, gameweek: int, cohort: str) -> EliteFigures | None:
        """One cohort's figures for ``gameweek``, or ``None`` if it was never sampled."""
        async with self._sessions() as session:
            sample = await session.get(EliteSample, (season, gameweek, cohort))
            if sample is None:
                return None
            owned = await session.scalars(
                select(EliteOwnership).where(
                    EliteOwnership.season == season,
                    EliteOwnership.gameweek == gameweek,
                    EliteOwnership.cohort == cohort,
                )
            )
            chips = await session.scalars(
                select(EliteChip).where(
                    EliteChip.season == season,
                    EliteChip.gameweek == gameweek,
                    EliteChip.cohort == cohort,
                )
            )
            return EliteFigures(
                cohort=cohort,
                gameweek=gameweek,
                cohort_size=sample.cohort_size,
                target_size=sample.target_size,
                sample_size=sample.sample_size,
                margin_of_error=sample.margin_of_error,
                footballers={
                    row.footballer_id: FootballerShares(
                        row.ownership, row.xi_share, row.captain_share, row.eo
                    )
                    for row in owned
                },
                chips={row.chip: row.share for row in chips},
                partial=sample.partial,
                read_late=sample.read_late,
            )
