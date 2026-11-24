"""Members and invites: who is allow-listed, and the single-use codes that let people in."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum, StrEnum
from typing import Any, Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from fplbot.store.schema import Invite, Member
from fplbot.store.seasons import season_of

# 12 random bytes: 96 bits, 16 URL-safe characters, well inside Telegram's 64-char start payload.
_CODE_BYTES = 12
# Arbitrary application-wide key for the Postgres advisory lock that serialises joins.
_JOIN_LOCK = 26_001


class Refusal(Enum):
    UNKNOWN = "unknown"
    USED = "used"
    EXPIRED = "expired"
    FULL = "full"


@dataclass(frozen=True)
class Joined:
    member_number: int


type Redemption = Joined | Refusal


class Goal(StrEnum):
    OVERALL = "overall"
    LEAGUE = "league"


@dataclass(frozen=True)
class GoalLeague:
    """The Mini-league a Member's Goal targets."""

    id: int
    kind: Literal["classic", "h2h"]
    name: str


@dataclass(frozen=True)
class MemberRecord:
    """Everything stored about a Member (``/settings`` shows it)."""

    number: int
    chat_id: int
    active: bool
    team_id: int | None
    team_name: str | None
    goal: Goal | None
    league: GoalLeague | None
    timezone: str | None
    alert_time: time

    @property
    def joining(self) -> bool:
        return not self.active


class MemberStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def issue_invite(self, now: datetime, valid_for: timedelta) -> str:
        """Create a single-use invite and return its code. Only the code's hash is stored."""
        code = secrets.token_urlsafe(_CODE_BYTES)
        async with self._sessions.begin() as session:
            session.add(
                Invite(
                    season=season_of(now),
                    code_hash=_hash(code),
                    created_at=now,
                    expires_at=now + valid_for,
                    used_at=None,
                )
            )
        return code

    async def redeem_invite(
        self, code: str, chat_id: int, now: datetime, member_cap: int
    ) -> Redemption:
        """Allow-list ``chat_id`` with ``code`` and use the code up, unless the code is unknown,
        used or expired, or ``member_cap`` Members already exist."""
        async with self._sessions.begin() as session:
            # Joins are serialised so two redemptions can't both take the last place.
            await session.execute(select(func.pg_advisory_xact_lock(_JOIN_LOCK)))
            invite = await session.scalar(
                select(Invite).where(Invite.code_hash == _hash(code)).with_for_update()
            )
            if invite is None:
                return Refusal.UNKNOWN
            if invite.used_at is not None:
                return Refusal.USED
            if now >= invite.expires_at:
                return Refusal.EXPIRED
            members = await session.scalar(select(func.count()).select_from(Member))
            if (members or 0) >= member_cap:
                return Refusal.FULL
            member = Member(season=season_of(now), chat_id=chat_id, joined_at=now)
            session.add(member)
            invite.used_at = now
            await session.flush()
            return Joined(member.id)

    async def member_number(self, chat_id: int) -> int | None:
        async with self._sessions() as session:
            return await session.scalar(select(Member.id).where(Member.chat_id == chat_id))

    async def get(self, chat_id: int) -> MemberRecord | None:
        async with self._sessions() as session:
            member = await session.scalar(select(Member).where(Member.chat_id == chat_id))
            return None if member is None else _record(member)

    async def linked_teams(self) -> list[tuple[int, int]]:
        """``(Member number, FPL team ID)`` of every Member with a linked team."""
        async with self._sessions() as session:
            rows = await session.execute(
                select(Member.id, Member.team_id)
                .where(Member.team_id.is_not(None))
                .order_by(Member.id)
            )
            return [(number, team_id) for number, team_id in rows.tuples() if team_id is not None]

    async def team_linked_elsewhere(self, team_id: int, chat_id: int) -> bool:
        """Whether another Member has already linked FPL team ``team_id``."""
        async with self._sessions() as session:
            other = await session.scalar(
                select(Member.id).where(Member.team_id == team_id, Member.chat_id != chat_id)
            )
            return other is not None

    async def link_team(self, chat_id: int, team_id: int, team_name: str) -> bool:
        """Link the team; ``False`` if another Member linked it first."""
        try:
            await self._update(chat_id, team_id=team_id, team_name=team_name)
        except IntegrityError:
            return False
        return True

    async def set_goal(self, chat_id: int, goal: Goal, league: GoalLeague | None) -> None:
        await self._update(
            chat_id,
            goal=goal.value,
            league_id=league.id if league else None,
            league_kind=league.kind if league else None,
            league_name=league.name if league else None,
        )

    async def set_timezone(self, chat_id: int, timezone: str) -> None:
        await self._update(chat_id, timezone=timezone)

    async def set_alert_time(self, chat_id: int, alert_time: time) -> None:
        await self._update(chat_id, alert_time=alert_time)

    async def activate(self, chat_id: int) -> None:
        await self._update(chat_id, status="active")

    async def delete(self, chat_id: int) -> None:
        """Hard-delete the Member. Rows in other tables go with it through their
        ``ON DELETE CASCADE`` foreign keys to ``members.id``. Invites are not linked to Members,
        so a used invite stays used."""
        async with self._sessions.begin() as session:
            await session.execute(delete(Member).where(Member.chat_id == chat_id))

    async def _update(self, chat_id: int, **values: Any) -> None:
        async with self._sessions.begin() as session:
            await session.execute(update(Member).where(Member.chat_id == chat_id).values(values))


def _record(member: Member) -> MemberRecord:
    league = None
    if member.league_id is not None and member.league_name is not None:
        kind: Literal["classic", "h2h"] = "h2h" if member.league_kind == "h2h" else "classic"
        league = GoalLeague(member.league_id, kind, member.league_name)
    return MemberRecord(
        number=member.id,
        chat_id=member.chat_id,
        active=member.status == "active",
        team_id=member.team_id,
        team_name=member.team_name,
        goal=Goal(member.goal) if member.goal else None,
        league=league,
        timezone=member.timezone,
        alert_time=member.alert_time,
    )


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
