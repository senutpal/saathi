"""Life-log models introduced by P11: contacts, habits, moods, expenses."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
