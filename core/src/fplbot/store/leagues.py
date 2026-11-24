"""Followed leagues (ticket 32): which Mini-league tables the bot keeps, for which Members.

A Followed league is a Mini-league of a Member with at most 50 managers (stored complete), or a
Member's Goal league above 50 (only its top 10 and the 20 managers directly above and below each
Member whose Goal it is). Leagues are de-duplicated across Members. Head-to-head leagues also keep
each Member's opponent per Gameweek.

Everything is recomputed together (``jobs/followed_leagues.py``) and written by ``replace`` in one
transaction: a league no Member follows any more is deleted then, with its table, so it is never
refreshed again. A Member's links and opponents reference ``members.id`` (ON DELETE CASCADE).
Only parsed fields are stored, never raw responses or managers' names.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import and_, delete, exists, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from fplbot.sources.fpl import FplStanding, LeagueKind
from fplbot.store.schema import (
    FollowedLeague,
    H2hOpponent,
    LeagueStanding,
    Member,
    MemberLeague,
)


@dataclass(frozen=True)
class LeagueSnapshot:
    """A Followed league's table as just read from FPL."""

    kind: LeagueKind
    league_id: int
    name: str
    complete: bool  # False: a Goal league above 50 managers, only the followed rows
    rows: tuple[FplStanding, ...]


@dataclass(frozen=True)
class Follow:
    member_number: int
    kind: LeagueKind
    league_id: int
    sort_order: int  # FPL's order of the Member's Mini-leagues


@dataclass(frozen=True)
class Opponent:
    """A Member's head-to-head opponent in one league and Gameweek; ``entry_id`` None: a bye."""

    member_number: int
    league_id: int
    gameweek: int
    entry_id: int | None
    team_name: str | None


@dataclass(frozen=True)
class LeagueTable:
    """A stored Followed league. ``rows`` are in FPL's order; for an incomplete league they skip
    positions (compare ``FplStanding.position``)."""

    kind: LeagueKind
    league_id: int
    name: str
    complete: bool
    gameweek: int | None  # the last deadline's Gameweek when the table was read
    gameweek_finished: bool  # whether that Gameweek was over then
    refreshed_at: datetime
    rows: tuple[FplStanding, ...]


class LeagueStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def replace(
        self,
        season: str,
        *,
        snapshots: Iterable[LeagueSnapshot],
        follows: Iterable[Follow],
        opponents: Iterable[Opponent],
        opponent_gameweeks: Iterable[int],
        gameweek: int | None,
        gameweek_finished: bool,
        at: datetime,
    ) -> None:
        """Make the stored Followed leagues of ``season`` exactly these: tables replaced, every
        Member's links replaced, leagues nobody follows deleted. Opponents are replaced for
        ``opponent_gameweeks``. Members who left meanwhile are skipped."""
        snapshots = list(snapshots)
        opponent_gameweeks = list(opponent_gameweeks)
        async with self._sessions.begin() as session:
            present = set(await session.scalars(select(Member.id)))
            follows = [f for f in follows if f.member_number in present]
            opponents = [o for o in opponents if o.member_number in present]

            await session.execute(delete(MemberLeague).where(MemberLeague.season == season))
            for snapshot in snapshots:
                key = (season, snapshot.kind, snapshot.league_id)
                values = {
                    "name": snapshot.name,
                    "complete": snapshot.complete,
                    "gameweek": gameweek,
                    "gameweek_finished": gameweek_finished,
                    "refreshed_at": at,
                }
                statement = insert(FollowedLeague).values(
                    season=season, kind=snapshot.kind, league_id=snapshot.league_id, **values
                )
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=["season", "kind", "league_id"], set_=values
                    )
                )
                await session.execute(
                    delete(LeagueStanding).where(
                        tuple_(LeagueStanding.season, LeagueStanding.kind, LeagueStanding.league_id)
                        == key
                    )
                )
                session.add_all(
                    LeagueStanding(
                        season=season,
                        kind=snapshot.kind,
                        league_id=snapshot.league_id,
                        position=row.position,
                        entry_id=row.entry_id,
                        team_name=row.team_name,
                        rank=row.rank,
                        last_rank=row.last_rank,
                        points=row.points,
                    )
                    for row in snapshot.rows
                )
            await session.flush()
            session.add_all(
                MemberLeague(
                    member_id=f.member_number,
                    season=season,
                    kind=f.kind,
                    league_id=f.league_id,
                    sort_order=f.sort_order,
                )
                for f in follows
            )
            await session.flush()
            await _delete_unfollowed(session)
            # Opponents: replaced for the Gameweeks just read, and dropped for any league the
            # Member no longer follows.
            await session.execute(
                delete(H2hOpponent).where(
                    H2hOpponent.season == season,
                    H2hOpponent.gameweek.in_(opponent_gameweeks)
                    | ~exists().where(
                        and_(
                            MemberLeague.member_id == H2hOpponent.member_id,
                            MemberLeague.season == H2hOpponent.season,
                            MemberLeague.kind == "h2h",
                            MemberLeague.league_id == H2hOpponent.league_id,
                        )
                    ),
                )
            )
            session.add_all(
                H2hOpponent(
                    member_id=o.member_number,
                    season=season,
                    league_id=o.league_id,
                    gameweek=o.gameweek,
                    opponent_entry_id=o.entry_id,
                    opponent_team_name=o.team_name,
                )
                for o in opponents
            )

    async def forget_unfollowed(self) -> None:
        """Delete every league no Member follows any more (e.g. right after a ``/leave``)."""
        async with self._sessions.begin() as session:
            await _delete_unfollowed(session)

    async def followed(self, member_number: int, season: str) -> list[LeagueTable]:
        """The Member's Followed leagues, in FPL's order of their Mini-leagues."""
        async with self._sessions() as session:
            leagues = (
                await session.scalars(
                    select(FollowedLeague)
                    .join(
                        MemberLeague,
                        (MemberLeague.season == FollowedLeague.season)
                        & (MemberLeague.kind == FollowedLeague.kind)
                        & (MemberLeague.league_id == FollowedLeague.league_id),
                    )
                    .where(MemberLeague.member_id == member_number, MemberLeague.season == season)
                    .order_by(MemberLeague.sort_order)
                )
            ).all()
            return [await self._table(session, league) for league in leagues]

    async def all_followed(self, season: str) -> list[LeagueTable]:
        """Every Followed league of the season (ticket 33: whose Rivals' picks to fetch)."""
        async with self._sessions() as session:
            leagues = (
                await session.scalars(
                    select(FollowedLeague)
                    .where(FollowedLeague.season == season)
                    .order_by(FollowedLeague.kind, FollowedLeague.league_id)
                )
            ).all()
            return [await self._table(session, league) for league in leagues]

    async def h2h_opponent(
        self, member_number: int, season: str, league_id: int, gameweek: int
    ) -> Opponent | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(H2hOpponent).where(
                    H2hOpponent.member_id == member_number,
                    H2hOpponent.season == season,
                    H2hOpponent.league_id == league_id,
                    H2hOpponent.gameweek == gameweek,
                )
            )
        if row is None:
            return None
        return Opponent(
            member_number, league_id, gameweek, row.opponent_entry_id, row.opponent_team_name
        )

    async def _table(self, session: AsyncSession, league: FollowedLeague) -> LeagueTable:
        rows = await session.scalars(
            select(LeagueStanding)
            .where(
                LeagueStanding.season == league.season,
                LeagueStanding.kind == league.kind,
                LeagueStanding.league_id == league.league_id,
            )
            .order_by(LeagueStanding.position)
        )
        return LeagueTable(
            kind=_kind(league.kind),
            league_id=league.league_id,
            name=league.name,
            complete=league.complete,
            gameweek=league.gameweek,
            gameweek_finished=league.gameweek_finished,
            refreshed_at=league.refreshed_at,
            rows=tuple(
                FplStanding(
                    position=row.position,
                    entry_id=row.entry_id,
                    team_name=row.team_name,
                    rank=row.rank,
                    last_rank=row.last_rank,
                    points=row.points,
                )
                for row in rows
            ),
        )


async def _delete_unfollowed(session: AsyncSession) -> None:
    """Leagues (of any season) with no Member link go, with their tables (ON DELETE CASCADE)."""
    await session.execute(
        delete(FollowedLeague).where(
            ~exists().where(
                and_(
                    MemberLeague.season == FollowedLeague.season,
                    MemberLeague.kind == FollowedLeague.kind,
                    MemberLeague.league_id == FollowedLeague.league_id,
                )
            ),
        )
    )


def _kind(value: str) -> Literal["classic", "h2h"]:
    return "h2h" if value == "h2h" else "classic"
