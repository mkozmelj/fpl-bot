"""Table definitions. Every table has a ``season`` column (spec, Implementation Decisions).

Schema changes go through a new Alembic revision in ``fplbot/store/migrations/versions`` and must
be backward-compatible with the previous image (ADR 0003: expand, then contract).
"""

from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
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


# --- Job completion rows (ticket 31): one per idempotent job and period ---


class JobCompletion(Base):
    """An idempotent job finished for one period: a Gameweek (``gw11``) for ``picks``, ``elite``
    and ``gw_final``, or a night (``2026-11-23``) for ``price_archive``. Written through
    ``store/completions.py``; the startup catch-up runs whatever has no row yet."""

    __tablename__ = "job_completions"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    job: Mapped[str] = mapped_column(String(32), primary_key=True)
    period: Mapped[str] = mapped_column(String(16), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# --- Followed leagues (ticket 32): the Mini-league tables kept for Members ---
# Read from public standings (Rivals' team names, ranks and points, never managers' names).
# Not in the Member backup: they are derived from FPL and recomputed. A Member's links go with
# them on /leave; a league no Member follows any more is deleted at the next recompute.

_FOLLOWED_LEAGUE_KEY = ["season", "kind", "league_id"]
_FOLLOWED_LEAGUE_REF = [f"followed_leagues.{column}" for column in _FOLLOWED_LEAGUE_KEY]


class FollowedLeague(Base):
    """A Mini-league at least one Member follows. ``complete`` is False for a Goal league above
    50 managers, of which only the top 10 and the 20 above and below each following Member are
    kept. ``gameweek`` is the last deadline's Gameweek when the table was read, and
    ``gameweek_finished`` whether that Gameweek was over then (the table is final for it)."""

    __tablename__ = "followed_leagues"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # "classic" or "h2h"
    league_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100))
    complete: Mapped[bool] = mapped_column(Boolean)
    gameweek: Mapped[int | None] = mapped_column(Integer)
    gameweek_finished: Mapped[bool] = mapped_column(Boolean)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LeagueStanding(Base):
    """One row of a Followed league's table. ``position`` is FPL's order (unique when ranks
    tie); ``points`` the table's ranking figure (FPL points; league points in head-to-head)."""

    __tablename__ = "league_standings"
    __table_args__ = (
        ForeignKeyConstraint(_FOLLOWED_LEAGUE_KEY, _FOLLOWED_LEAGUE_REF, ondelete="CASCADE"),
    )

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    league_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    position: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    entry_id: Mapped[int] = mapped_column(BigInteger)
    team_name: Mapped[str] = mapped_column(String(100))
    rank: Mapped[int] = mapped_column(Integer)
    last_rank: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer)


class MemberLeague(Base):
    """A Member follows a league. ``sort_order`` is FPL's order of the Member's Mini-leagues
    (the first stands in for the Goal league when the Goal is Overall rank)."""

    __tablename__ = "member_leagues"
    __table_args__ = (
        ForeignKeyConstraint(_FOLLOWED_LEAGUE_KEY, _FOLLOWED_LEAGUE_REF, ondelete="CASCADE"),
    )

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    league_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    sort_order: Mapped[int] = mapped_column(Integer)


class H2hOpponent(Base):
    """A Member's opponent in one of their followed head-to-head leagues in one Gameweek.
    ``opponent_entry_id`` is NULL for a bye (FPL's "average" opponent)."""

    __tablename__ = "h2h_opponents"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    league_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    gameweek: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    opponent_entry_id: Mapped[int | None] = mapped_column(BigInteger)
    opponent_team_name: Mapped[str | None] = mapped_column(String(100))
