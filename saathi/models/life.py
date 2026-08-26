"""Life-log models introduced by P11: contacts, habits, moods, expenses."""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin


class Contact(TimestampMixin, db.Model):
    __tablename__ = "contacts"
    __table_args__ = (Index("ix_contacts_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    dob: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class Habit(TimestampMixin, db.Model):
    __tablename__ = "habits"
    __table_args__ = (Index("ix_habits_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    # KEY into the fixed palette dict (templates map key -> literal Tailwind
    # classes; interpolated bg-{color}-500 strings never survive JIT purging)
    color: Mapped[str | None] = mapped_column(String(10))

    logs: Mapped[list[HabitLog]] = relationship(passive_deletes=True)


class HabitLog(db.Model):
    """A done-day fact; no audit stamps (rows are inserted/deleted, never edited)."""

    __tablename__ = "habit_logs"
    __table_args__ = (
        UniqueConstraint("habit_id", "log_date", name="uq_habit_logs_habit_date"),
        Index("ix_habit_logs_habit", "habit_id", "log_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date)


class Mood(db.Model):
    """One row per user per day (DB-enforced); score 1-5 CHECK reserved since B04."""

    __tablename__ = "moods"
    __table_args__ = (
        UniqueConstraint("user_id", "mood_date", name="uq_moods_user_date"),
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_moods_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # NOT named "date": SQL keyword + shadows the python date type
    mood_date: Mapped[date] = mapped_column(Date)
    score: Mapped[int] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text)
