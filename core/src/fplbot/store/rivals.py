"""Rival picks (ticket 33): the Squads of the Rivals in the Followed leagues, per Gameweek.

A Rival here is any team in a stored Followed-league table, or a Member's stored head-to-head
opponent, that is not a Member's own team (a Member's Squad is in ``member_picks`` already). Rows
are kept for the season and pruned together with the leagues (``store/leagues.py``): a Rival no
stored table or opponent row holds any more loses their picks. Only team IDs are stored.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select, union
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.sources.fpl import FplPicks
from fplbot.store.schema import H2hOpponent, LeagueStanding, Member, MemberPick, RivalPick

XI_SLOTS = 11


@dataclass(frozen=True)
class TeamPicks:
    """Who a team started and captained at one Gameweek's deadline."""

    xi: frozenset[int]
    captain: int | None


class RivalPicksStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def rival_entries(self, season: str) -> list[int]:
        """Every Rival's team ID: teams in a stored table or opponent row, minus Members'."""
        standings = select(LeagueStanding.entry_id.label("entry_id")).where(
            LeagueStanding.season == season
        )
        opponents = select(H2hOpponent.opponent_entry_id.label("entry_id")).where(
            H2hOpponent.season == season, H2hOpponent.opponent_entry_id.is_not(None)
        )
        async with self._sessions() as session:
            teams = set(await session.scalars(union(standings, opponents)))
            members = set(
                await session.scalars(select(Member.team_id).where(Member.team_id.is_not(None)))
            )
        return sorted(team for team in teams - members if team is not None)

    async def missing(self, season: str, gameweek: int, entries: Iterable[int]) -> list[int]:
        """Which of ``entries`` have no picks stored for ``gameweek``."""
        wanted = list(entries)
        async with self._sessions() as session:
            stored = set(
                await session.scalars(
                    select(RivalPick.entry_id)
                    .where(
                        RivalPick.season == season,
                        RivalPick.gameweek == gameweek,
                        RivalPick.entry_id.in_(wanted),
                    )
                    .distinct()
                )
            )
        return [entry for entry in wanted if entry not in stored]

    async def save(self, season: str, entry_id: int, picks: FplPicks) -> None:
        """Store a Rival's Squad at ``picks.gameweek``'s deadline, replacing any stored one."""
        async with self._sessions.begin() as session:
            await session.execute(
                delete(RivalPick).where(
                    RivalPick.season == season,
                    RivalPick.entry_id == entry_id,
                    RivalPick.gameweek == picks.gameweek,
                )
            )
            session.add_all(
                RivalPick(
                    season=season,
                    entry_id=entry_id,
                    gameweek=picks.gameweek,
                    slot=pick.slot,
                    footballer_id=pick.footballer_id,
                    multiplier=pick.multiplier,
                    is_captain=pick.is_captain,
                    is_vice_captain=pick.is_vice_captain,
                )
                for pick in picks.picks
            )

    async def team_picks(
        self, season: str, gameweek: int, entries: Iterable[int]
    ) -> dict[int, TeamPicks]:
        """The stored picks at ``gameweek``'s deadline of each of ``entries`` that has them: a
        Member's team from their own Squad, anyone else's from the Rival picks."""
        wanted = list(entries)
        rows: list[tuple[int, int, int, bool]] = []
        async with self._sessions() as session:
            rival = await session.execute(
                select(
                    RivalPick.entry_id,
                    RivalPick.slot,
                    RivalPick.footballer_id,
                    RivalPick.is_captain,
                ).where(
                    RivalPick.season == season,
                    RivalPick.gameweek == gameweek,
                    RivalPick.entry_id.in_(wanted),
                )
            )
            rows.extend(rival.tuples())
            member = await session.execute(
                select(
                    Member.team_id, MemberPick.slot, MemberPick.footballer_id, MemberPick.is_captain
                )
                .join(MemberPick, MemberPick.member_id == Member.id)
                .where(
                    MemberPick.season == season,
                    MemberPick.gameweek == gameweek,
                    Member.team_id.in_(wanted),
                )
            )
            members = [
                (team, slot, f, c) for team, slot, f, c in member.tuples() if team is not None
            ]
        member_teams = {team for team, *_ in members}
        rows = [row for row in rows if row[0] not in member_teams] + members
        xi: dict[int, set[int]] = {}
        captain: dict[int, int] = {}
        for entry, slot, footballer, is_captain in rows:
            starting = xi.setdefault(entry, set())
            if slot <= XI_SLOTS:
                starting.add(footballer)
            if is_captain:
                captain[entry] = footballer
        return {entry: TeamPicks(frozenset(ids), captain.get(entry)) for entry, ids in xi.items()}
