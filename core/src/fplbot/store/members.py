"""Members and invites: who is allow-listed, and the single-use codes that let people in."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import func, select
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


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
