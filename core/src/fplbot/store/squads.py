"""A Member's season: FPL history per Gameweek and the Squad picked at each deadline.

Rows reference ``members.id`` with ON DELETE CASCADE, so ``/leave`` removes them. A write for a
Member who has just left returns ``False`` instead of failing (a background job may still be
running when they leave).
"""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.sources.fpl import FplHistory, FplPicks
from fplbot.store.schema import Footballer, MemberGameweek, MemberPick

XI_SIZE = 11


@dataclass(frozen=True)
class SquadPick:
    footballer_id: int
    name: str
    position: str | None  # GKP, DEF, MID or FWD; None if the Footballer is not in reference data
    is_captain: bool
    is_vice_captain: bool


@dataclass(frozen=True)
class Squad:
    """A Squad at one Gameweek's deadline, in FPL's order."""

    gameweek: int
    xi: tuple[SquadPick, ...]
    bench: tuple[SquadPick, ...]  # in bench order


class SquadStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def save_history(self, member_number: int, season: str, history: FplHistory) -> bool:
        """Store (or update) each Gameweek of the Member's history. ``False`` if the Member is
        gone."""
        rows = [
            {
                "member_id": member_number,
                "season": season,
                "gameweek": g.gameweek,
                "points": g.points,
                "total_points": g.total_points,
                "rank": g.rank,
                "overall_rank": g.overall_rank,
                "bank": g.bank,
                "value": g.value,
                "transfers": g.transfers,
                "transfers_cost": g.transfers_cost,
                "points_on_bench": g.points_on_bench,
                "chip": g.chip,
            }
            for g in history.gameweeks
        ]
        if not rows:
            return True
        statement = insert(MemberGameweek).values(rows)
        keys = ("member_id", "season", "gameweek")
        updated = {k: statement.excluded[k] for k in rows[0] if k not in keys}
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    statement.on_conflict_do_update(index_elements=keys, set_=updated)
                )
        except IntegrityError:
            return False
        return True

    async def save_picks(self, member_number: int, season: str, picks: FplPicks) -> bool:
        """Store the Member's Squad at ``picks.gameweek``'s deadline, replacing any stored one.
        ``False`` if the Member is gone."""
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    delete(MemberPick).where(
                        MemberPick.member_id == member_number,
                        MemberPick.season == season,
                        MemberPick.gameweek == picks.gameweek,
                    )
                )
                session.add_all(
                    MemberPick(
                        member_id=member_number,
                        season=season,
                        gameweek=picks.gameweek,
                        slot=pick.slot,
                        footballer_id=pick.footballer_id,
                        multiplier=pick.multiplier,
                        is_captain=pick.is_captain,
                        is_vice_captain=pick.is_vice_captain,
                    )
                    for pick in picks.picks
                )
        except IntegrityError:
            return False
        return True

    async def latest_squad(
        self, member_number: int, season: str, up_to_gameweek: int
    ) -> Squad | None:
        """The most recent stored Squad at or before ``up_to_gameweek``'s deadline (older than
        that Gameweek when its picks are not stored yet), or ``None``."""
        async with self._sessions() as session:
            gameweek = await session.scalar(
                select(func.max(MemberPick.gameweek)).where(
                    MemberPick.member_id == member_number,
                    MemberPick.season == season,
                    MemberPick.gameweek <= up_to_gameweek,
                )
            )
        return None if gameweek is None else await self.squad(member_number, season, gameweek)

    async def squad(self, member_number: int, season: str, gameweek: int) -> Squad | None:
        """The Member's Squad at ``gameweek``'s deadline, or ``None`` if none is stored."""
        async with self._sessions() as session:
            rows = await session.execute(
                select(MemberPick, Footballer.web_name, Footballer.position)
                .outerjoin(
                    Footballer,
                    (Footballer.season == MemberPick.season)
                    & (Footballer.id == MemberPick.footballer_id),
                )
                .where(
                    MemberPick.member_id == member_number,
                    MemberPick.season == season,
                    MemberPick.gameweek == gameweek,
                )
                .order_by(MemberPick.slot)
            )
            picks = [
                SquadPick(
                    footballer_id=pick.footballer_id,
                    name=name or f"Footballer {pick.footballer_id}",
                    position=position,
                    is_captain=pick.is_captain,
                    is_vice_captain=pick.is_vice_captain,
                )
                for pick, name, position in rows.tuples()
            ]
        if not picks:
            return None
        return Squad(gameweek, tuple(picks[:XI_SIZE]), tuple(picks[XI_SIZE:]))
