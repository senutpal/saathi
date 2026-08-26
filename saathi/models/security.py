"""Security ledger models: login lockout, backup codes, sign-in history.

User-level security columns live on identity.User.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin


class LoginAttempt(db.Model):
    """One row per failed login POST — the durable lockout ledger.

    Keyed on the lowercased submitted email only. That means anyone who
    knows a victim's email can hold their logins shut at 5 failures/15min
    (anti-DoS trade-off accepted for course scope, B16 §6); a full success
    clears the email's rows instead of flipping flags, so no reset logic.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_email_time", "email", "attempted_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    attempted_at: Mapped[datetime] = mapped_column(DateTime)
    success: Mapped[bool] = mapped_column(default=False)


class BackupCode(TimestampMixin, db.Model):
    """Single-use recovery code for 2FA; only the SHA-256 hex is stored."""

    __tablename__ = "backup_codes"
    __table_args__ = (
        Index(
            "ix_backup_codes_user_spendable",
            "user_id",
            sqlite_where=text("used_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class LoginRecord(db.Model):
    """One row per successful login — feeds the Security page sign-in list."""

    __tablename__ = "logins"
    __table_args__ = (Index("ix_logins_user_time", "user_id", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(200))
