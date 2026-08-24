"""User-content models: notes, tags, uploads and the activity trail."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin

if TYPE_CHECKING:
    from .identity import User
    from .scheduling import Event


class Note(TimestampMixin, db.Model):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="notes")
    linked_event: Mapped[Event | None] = relationship(back_populates="notes")
    tags: Mapped[list[Tag]] = relationship(
        secondary="note_tags", lazy="selectin", back_populates="notes"
    )


class Tag(TimestampMixin, db.Model):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tags_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(40))

    notes: Mapped[list[Note]] = relationship(secondary="note_tags", back_populates="tags")


class NoteTag(db.Model):
    __tablename__ = "note_tags"
    __table_args__ = (Index("ix_note_tags_tag", "tag_id"),)

    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Upload(TimestampMixin, db.Model):
    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_uploads_size"),
        Index("ix_uploads_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="uploads")


class ActivityLog(db.Model):
    """Immutable audit trail; no updated_at by design (rows never change)."""

    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_activity_user", "user_id", "occurred_at"),
        Index("ix_activitylog_type", "activity_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    activity_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(120))
    details: Mapped[str | None] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="activities")
