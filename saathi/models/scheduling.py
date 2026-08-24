"""Reminder scheduling models: events and their notifications."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin

if TYPE_CHECKING:
    from .content import Note
    from .identity import User


class Event(TimestampMixin, db.Model):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_time", "user_id", "status", "event_at"),
        CheckConstraint(
            "alert_lead_minutes >= 0 AND alert_lead_minutes <= 10080",
            name="ck_events_alert_lead",
        ),
        CheckConstraint(
            "repeat_rule IN ('none','daily','weekly','monthly','yearly')",
            name="ck_events_repeat_rule",
        ),
        CheckConstraint(
            "status IN ('scheduled','fired','fired_late','missed','cancelled')",
            name="ck_events_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    event_at: Mapped[datetime] = mapped_column(DateTime)
    repeat_rule: Mapped[str] = mapped_column(String(20), default="none")
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    fired_at: Mapped[datetime | None] = mapped_column(DateTime)
    alert_lead_minutes: Mapped[int] = mapped_column(default=30)

    user: Mapped[User] = relationship(back_populates="events")
    notes: Mapped[list[Note]] = relationship(back_populates="linked_event")
    notifications: Mapped[list[Notification]] = relationship(back_populates="event")


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            sqlite_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="notifications")
    event: Mapped[Event | None] = relationship(back_populates="notifications")
