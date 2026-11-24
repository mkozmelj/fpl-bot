"""Table definitions. Every table has a ``season`` column (spec, Implementation Decisions).

Schema changes go through a new Alembic revision in ``fplbot/store/migrations/versions`` and must
be backward-compatible with the previous image (ADR 0003: expand, then contract).
"""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
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


# --- Reference data (ticket 30): kept across seasons, keyed by (season, FPL id) ---
# Written from bootstrap-static and fixtures/ by ``store/reference.py``; never raw responses.


class Club(Base):
    __tablename__ = "clubs"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(50))
    short_name: Mapped[str] = mapped_column(String(8))


class Footballer(Base):
    __tablename__ = "footballers"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    web_name: Mapped[str] = mapped_column(String(50))
    first_name: Mapped[str] = mapped_column(String(100))
    second_name: Mapped[str] = mapped_column(String(100))
    club_id: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(3))  # GKP, DEF, MID or FWD
    now_cost: Mapped[int] = mapped_column(Integer)  # tenths of a million


class Gameweek(Base):
    __tablename__ = "gameweeks"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished: Mapped[bool] = mapped_column(Boolean)
    data_checked: Mapped[bool] = mapped_column(Boolean)


class Fixture(Base):
    __tablename__ = "fixtures"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    gameweek: Mapped[int | None] = mapped_column(Integer)  # NULL while unscheduled
    kickoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_club_id: Mapped[int] = mapped_column(Integer)
    away_club_id: Mapped[int] = mapped_column(Integer)
    home_difficulty: Mapped[int | None] = mapped_column(Integer)
    away_difficulty: Mapped[int | None] = mapped_column(Integer)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    finished: Mapped[bool] = mapped_column(Boolean)


# --- A Member's season (ticket 30): deleted with the Member (``/leave``) ---


class MemberGameweek(Base):
    """One row of the Member's FPL history. Money in tenths of a million."""

    __tablename__ = "member_gameweeks"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    gameweek: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    points: Mapped[int] = mapped_column(Integer)
    total_points: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    overall_rank: Mapped[int | None] = mapped_column(Integer)
    bank: Mapped[int] = mapped_column(Integer)
    value: Mapped[int] = mapped_column(Integer)
    transfers: Mapped[int] = mapped_column(Integer)
    transfers_cost: Mapped[int] = mapped_column(Integer)
    points_on_bench: Mapped[int] = mapped_column(Integer)
    chip: Mapped[str | None] = mapped_column(String(16))


class MemberPick(Base):
    """One of the 15 picks of a Member's Squad at a Gameweek's deadline. ``slot`` 1-11 is the
    XI in formation order, 12-15 the bench in order."""

    __tablename__ = "member_picks"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    gameweek: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    footballer_id: Mapped[int] = mapped_column(Integer)
    multiplier: Mapped[int] = mapped_column(Integer)
    is_captain: Mapped[bool] = mapped_column(Boolean)
    is_vice_captain: Mapped[bool] = mapped_column(Boolean)


class WatchedFootballer(Base):
    """One Footballer on a Member's Watch list (ticket 29). ``footballer_id`` is FPL's element id,
    which FPL renumbers every season, so a row only counts in its own ``season``."""

    __tablename__ = "watch_list"
    __table_args__ = (UniqueConstraint("member_id", "season", "footballer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), index=True
    )
    footballer_id: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MemberBackupMessage(Base):
    """A backup document the bot sent to the owner's chat (ticket 39), so the oldest can be
    deleted once more than the last 7 are there. Not itself part of the backup."""

    __tablename__ = "member_backups"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    message_id: Mapped[int] = mapped_column(BigInteger)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OwnerNotice(Base):
    """A one-time owner DM that was sent (e.g. "backup skipped: no key"), so a restart does not
    repeat it. Removing the row lets the notice be sent again."""

    __tablename__ = "owner_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    notice: Mapped[str] = mapped_column(String(32), unique=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# --- Price history (ticket 37): kept across seasons, not Member data ---
# Footballer ids are FPL element ids, renumbered every season, so each row counts only in its
# own ``season``. Written by ``store/price_history.py``; never raw responses.


class PriceSnapshot(Base):
    """One Footballer's price-change state at one evening snapshot time (18:00, 20:00, 22:00,
    23:00 and 23:45 UK). ``taken_at`` is the planned snapshot time."""

    __tablename__ = "price_snapshots"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    footballer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    price: Mapped[int] = mapped_column(SmallInteger)  # tenths of a million
    # FPL's progress towards a change, in tenths of a percent (-974 is -97.4%).
    percent: Mapped[int | None] = mapped_column(SmallInteger)
    hourly_rate: Mapped[int | None] = mapped_column(Integer)
    # Likelihood codes (-5..+5) for tonight's, tomorrow night's and the next night's update.
    likelihood_tonight: Mapped[int | None] = mapped_column(SmallInteger)
    likelihood_tomorrow: Mapped[int | None] = mapped_column(SmallInteger)
    likelihood_after: Mapped[int | None] = mapped_column(SmallInteger)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibrating: Mapped[bool | None] = mapped_column(Boolean)


class PriceChange(Base):
    """An actual Price change, from the nightly ``stats/price-changes/`` archive. ``night`` is
    the UK date before the 00:00 UK update that made it."""

    __tablename__ = "price_changes"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    footballer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    night: Mapped[date] = mapped_column(Date, index=True)
    gameweek: Mapped[int | None] = mapped_column(Integer)
    club_id: Mapped[int | None] = mapped_column(Integer)
    cost_before: Mapped[int] = mapped_column(SmallInteger)
    cost_after: Mapped[int] = mapped_column(SmallInteger)


class PriceArchiveNight(Base):
    """A night whose ``stats/price-changes/`` archive has been stored: re-runs are no-ops, and
    only such nights are scored by ``/accuracy`` (a missing change then means "no change")."""

    __tablename__ = "price_archive_nights"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    night: Mapped[date] = mapped_column(Date, primary_key=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PricePrediction(Base):
    """FPL's likelihood codes for one Footballer at the night's first Price-alert time, kept to
    score the predictor against the actual change (``/accuracy``)."""

    __tablename__ = "price_predictions"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    night: Mapped[date] = mapped_column(Date, primary_key=True)
    footballer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    made_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tonight: Mapped[int | None] = mapped_column(SmallInteger)
    tomorrow: Mapped[int | None] = mapped_column(SmallInteger)


class FootballerNews(Base):
    """A change of a Footballer's FPL status flag (a/d/i/s/u/n) or news text, logged only when
    it differs from the Footballer's previous row (the first read logs everyone once)."""

    __tablename__ = "footballer_news"
    __table_args__ = (Index("ix_footballer_news_latest", "season", "footballer_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[str] = mapped_column(String(7))
    footballer_id: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(8))
    news: Mapped[str] = mapped_column(Text)
