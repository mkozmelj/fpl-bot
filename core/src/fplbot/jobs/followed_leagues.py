"""Recomputing the Followed leagues (ticket 32) and reading their tables.

Followed leagues (spec, Sources and ingestion): every Mini-league of each Member with at most 50
managers, de-duplicated across Members, plus each Member's head-to-head opponent per Gameweek. A
Goal league above 50 is followed as its top 10 plus the 20 managers directly above and the 20
directly below each Member whose Goal it is. A league above 50 that is nobody's Goal is not
followed.

One recompute covers every Member with a linked team: their Mini-leagues (``entry/{id}/``), each
league's table (``leagues-{kind}/{id}/standings/``, 50 rows a page; a league fits in one page
exactly when it has at most 50 managers) and, for head-to-head leagues, the opponent in the last
and the next deadline's Gameweek. Nothing is written until everything is read, so a failed run
leaves the previous tables in place. It runs on join and on a Goal change (``recompute_soon``)
and from the Gameweek-final job after each Gameweek. Afterwards it reads the last deadline's
picks of any Rival that has none yet (ticket 33, ``jobs/rival_picks.py``).
"""

import asyncio
import logging
from dataclasses import dataclass

from fplbot.clock import Clock
from fplbot.jobs.rival_picks import RivalPicks
from fplbot.jobs.runner import JobRunner, waiting_while_updating
from fplbot.sources.fpl import (
    STANDINGS_PAGE_SIZE,
    FplLeague,
    FplSource,
    FplStanding,
    FplStandings,
    LeagueKind,
    Priority,
)
from fplbot.store.leagues import Follow, LeagueSnapshot, LeagueStore, Opponent
from fplbot.store.members import Goal, MemberRecord, MemberStore
from fplbot.store.reference import ReferenceStore
from fplbot.store.seasons import season_of

log = logging.getLogger(__name__)

LEAGUES_JOB = "leagues"
BIG_LEAGUE_TOP = 10
BIG_LEAGUE_AROUND = 20

type LeagueKey = tuple[LeagueKind, int]


@dataclass(frozen=True)
class _Following:
    member: MemberRecord
    team_id: int
    leagues: tuple[FplLeague, ...]

    def goal(self) -> LeagueKey | None:
        league = self.member.league
        if self.member.goal is not Goal.LEAGUE or league is None:
            return None
        return (league.kind, league.id)


class FollowedLeagues:
    def __init__(
        self,
        *,
        clock: Clock,
        members: MemberStore,
        reference: ReferenceStore,
        leagues: LeagueStore,
        jobs: JobRunner,
        rival_picks: RivalPicks,
    ) -> None:
        self._clock = clock
        self._rival_picks = rival_picks
        self._members = members
        self._reference = reference
        self._leagues = leagues
        self._jobs = jobs
        self._lock = asyncio.Lock()
        self._again = False
        self._task: asyncio.Task[bool] | None = None

    def recompute_soon(self) -> None:
        """Recompute in the background (after a join or a Goal change). Requests while one runs
        are merged into one more run after it."""
        self._again = True
        if self._task is None or self._task.done():
            job = waiting_while_updating(self._recompute_while_asked, self._clock)
            self._task = self._jobs.start(LEAGUES_JOB, job, Priority.ROUTINE)

    async def _recompute_while_asked(self, fpl: FplSource) -> None:
        while self._again:
            self._again = False
            await self.recompute(fpl)

    async def recompute(self, fpl: FplSource) -> None:
        """Read every Member's Followed leagues from FPL and store them. Raises ``FplError``."""
        async with self._lock:
            now = self._clock.now()
            season = season_of(now)
            await self._reference.ensure_loaded(fpl)  # e.g. on the first join: Gameweeks
            deadlines = await self._reference.deadlines(now)
            followings: list[_Following] = []
            for member in await self._members.with_teams():
                if member.team_id is None:
                    continue
                team = await fpl.team(member.team_id)
                leagues = team.mini_leagues if team is not None else ()
                followings.append(_Following(member, member.team_id, leagues))

            snapshots: list[LeagueSnapshot] = []
            followers: dict[LeagueKey, list[_Following]] = {}
            for key in _distinct_leagues(followings):
                snapshot, who = await self._read_league(fpl, key, followings)
                if snapshot is not None:
                    snapshots.append(snapshot)
                    followers[key] = who

            follows = [
                Follow(f.member.number, league.kind, league.id, order)
                for f in followings
                for order, league in enumerate(f.leagues)
                if f in followers.get((league.kind, league.id), [])
            ]
            gameweeks = sorted({g.id for g in (deadlines.last, deadlines.next) if g is not None})
            opponents: list[Opponent] = []
            for f in followings:
                for league in f.leagues:
                    if league.kind != LeagueKind.H2H or f not in followers.get(
                        (LeagueKind.H2H, league.id), []
                    ):
                        continue
                    for gameweek in gameweeks:
                        if opponent := await _opponent(fpl, f, league.id, gameweek):
                            opponents.append(opponent)
            last = deadlines.last
            await self._leagues.replace(
                season,
                snapshots=snapshots,
                follows=follows,
                opponents=opponents,
                opponent_gameweeks=gameweeks,
                gameweek=last.id if last else None,
                gameweek_finished=bool(last and last.finished),
                at=now,
            )
            log.info("followed leagues recomputed: %d leagues", len(snapshots))
        if last is not None:
            # New Rivals (a Member joined or switched Goal) get their last-deadline Squads.
            await self._rival_picks.fetch_missing(fpl, season, last.id)

    async def _read_league(
        self, fpl: FplSource, key: LeagueKey, followings: list[_Following]
    ) -> tuple[LeagueSnapshot | None, list[_Following]]:
        """The league's table to keep and who follows it; ``None`` if nobody does."""
        kind, league_id = key
        members = [f for f in followings if any((x.kind, x.id) == key for x in f.leagues)]
        first = await fpl.standings(kind, league_id)
        if first is None:
            return None, []  # gone, or not visible to us
        if not first.has_next:
            return LeagueSnapshot(kind, league_id, first.league_name, True, first.rows), members
        goal_of = [f for f in members if f.goal() == key]
        if not goal_of:
            return None, []
        pages = _Pages(fpl, kind, league_id, {1: first})
        rows: dict[int, FplStanding] = {row.position: row for row in first.rows[:BIG_LEAGUE_TOP]}
        for following in goal_of:
            for row in await pages.around(following):
                rows[row.position] = row
        snapshot = LeagueSnapshot(
            kind, league_id, first.league_name, False, tuple(rows[p] for p in sorted(rows))
        )
        return snapshot, goal_of


class _Pages:
    """The pages of one big league read so far in a recompute (each page read at most once)."""

    def __init__(
        self, fpl: FplSource, kind: LeagueKind, league_id: int, pages: dict[int, FplStandings]
    ) -> None:
        self._fpl = fpl
        self._kind: LeagueKind = kind
        self._league_id = league_id
        self._pages = pages

    async def page(self, number: int) -> FplStandings | None:
        if number not in self._pages:
            page = await self._fpl.standings(self._kind, self._league_id, number)
            if page is None:
                return None
            self._pages[number] = page
        return self._pages[number]

    async def around(self, following: _Following) -> list[FplStanding]:
        """The Member's row and the ``BIG_LEAGUE_AROUND`` rows either side of it."""
        position = await self._find(following)
        if position is None:
            log.info("member %d not found in their Goal league table", following.member.number)
            return []
        low = max(1, position - BIG_LEAGUE_AROUND)
        high = position + BIG_LEAGUE_AROUND
        rows: list[FplStanding] = []
        for number in range(_page_of(low), _page_of(high) + 1):
            page = await self.page(number)
            if page is None:
                break
            rows.extend(r for r in page.rows if low <= r.position <= high)
            if not page.has_next:
                break
        return rows

    async def _find(self, following: _Following) -> int | None:
        """The Member's position, looked for on the page their reported rank points to and the
        pages either side (ranks move between FPL's updates)."""
        rank = next(
            (x.entry_rank for x in following.leagues if (x.kind, x.id) == following.goal()), None
        )
        guess = _page_of(rank) if rank else 1
        for number in (guess, guess - 1, guess + 1):
            if number < 1:
                continue
            page = await self.page(number)
            if page is None:
                continue
            for row in page.rows:
                if row.entry_id == following.team_id:
                    return row.position
        return None


def _page_of(position: int) -> int:
    return (position - 1) // STANDINGS_PAGE_SIZE + 1


def _distinct_leagues(followings: list[_Following]) -> list[LeagueKey]:
    seen: dict[LeagueKey, None] = {}
    for following in followings:
        for league in following.leagues:
            seen.setdefault((league.kind, league.id), None)
    return list(seen)


async def _opponent(
    fpl: FplSource, following: _Following, league_id: int, gameweek: int
) -> Opponent | None:
    matches = await fpl.h2h_matches(league_id, gameweek, following.team_id)
    for match in matches or ():
        sides = ((match.entry_1, match.entry_1_name), (match.entry_2, match.entry_2_name))
        for (me, _), (other, other_name) in (sides, sides[::-1]):
            if me == following.team_id:
                name = other_name if other is not None else None
                return Opponent(following.member.number, league_id, gameweek, other, name)
    return None
