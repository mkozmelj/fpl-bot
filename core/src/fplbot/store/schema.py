"""Table definitions. Every table has a ``season`` column (spec, Implementation Decisions).

Schema changes go through a new Alembic revision in ``fplbot/store/migrations/versions`` and must
be backward-compatible with the previous image (ADR 0003: expand, then contract).
"""

from datetime import datetime, time

from sqlalchemy import BigInteger, DateTime, String, Time, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Member(Base):
    """An allow-listed private chat. ``id`` is the internal Member number: the only identifier
    that may appear in logs.

    ``status`` is ``joining`` until setup (team, Goal, timezone) is complete, then ``active``.
    Tables holding a Member's data reference ``members.id`` with ``ondelete="CASCADE"`` so that
    ``/leave`` (which deletes this row) hard-deletes them too.
    """

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), server_default="joining")
    # The linked FPL team. Only its ID and name are kept, never the manager's name.
    team_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    team_name: Mapped[str | None] = mapped_column(String(100))
    # "overall" or "league"; for "league" the chosen Mini-league ("classic" or "h2h").
    goal: Mapped[str | None] = mapped_column(String(16))
    league_id: Mapped[int | None] = mapped_column(BigInteger)
    league_kind: Mapped[str | None] = mapped_column(String(8))
    league_name: Mapped[str | None] = mapped_column(String(100))
    # IANA zone name, e.g. "Europe/London".
    timezone: Mapped[str | None] = mapped_column(String(64))
    # Price alert time in the Member's own timezone.
    alert_time: Mapped[time] = mapped_column(Time, server_default=text("'20:00'"))


class Invite(Base):
    """A single-use invite. Only the SHA-256 of the code is stored, never the code itself. Used
    invites are kept (not linked to the Member) so a code stays used after the Member leaves."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
