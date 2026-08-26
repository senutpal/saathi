"""Shared model primitives: naive-UTC clock and audit-stamp mixin."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Naive UTC now — the single app-side clock convention (never datetime.utcnow)."""
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
