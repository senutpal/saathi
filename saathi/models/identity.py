"""Auth identity and profile models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .base import TimestampMixin

if TYPE_CHECKING:
    from .content import ActivityLog, Note, Upload
    from .scheduling import Event, Notification


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(password_hash) > 0", name="ck_users_password_hash"),
        Index("ix_users_alive", "id", sqlite_where=text("deleted_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    ics_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    twofa_enabled: Mapped[bool] = mapped_column(default=False)
    session_invalid_before: Mapped[datetime | None] = mapped_column(DateTime)
    digest_enabled: Mapped[bool] = mapped_column(default=False)
    digest_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    education_entries: Mapped[list[EducationEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    work_entries: Mapped[list[WorkEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notes: Mapped[list[Note]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    uploads: Mapped[list[Upload]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    activities: Mapped[list[ActivityLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Profile(TimestampMixin, db.Model):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    sex: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(140))
    skills_csv: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    likes: Mapped[str | None] = mapped_column(Text)
    dislikes: Mapped[str | None] = mapped_column(Text)
    public_token: Mapped[str | None] = mapped_column(String(43), unique=True)
    share_enabled: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User] = relationship(back_populates="profile")


class EducationEntry(TimestampMixin, db.Model):
    __tablename__ = "education_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    institution: Mapped[str] = mapped_column(String(150))
    qualification: Mapped[str] = mapped_column(String(150))
    field_of_study: Mapped[str | None] = mapped_column(String(150))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="education_entries")


class WorkEntry(TimestampMixin, db.Model):
    __tablename__ = "work_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(150))
    location: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="work_entries")
