"""Per-account login lockout over the login_attempts ledger.

Division of labor (ADR-017): flask-limiter is the fast IP-based brake
(5/min per client); this is the slow per-account counter that works across
IPs (5 failures / 15 rolling minutes). Both stay on — they answer different
attacks. The ledger is keyed on the lowercased submitted email only, which
means an attacker can deliberately lock a victim out (anti-DoS trade-off,
accepted for course scope and documented in the report; B16 §6).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

from ...extensions import db
from ...models import LoginAttempt
from ...models.base import utcnow

LOCKOUT_LIMIT = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
# Phase S6 retention (>30d of viva-demoable history) beats B16 sketch's 24h.
PRUNE_AFTER = timedelta(days=30)


def normalize(email: str) -> str:
    """The ledger key: stripped lowercase email."""
    return (email or "").strip().lower()


def failure_count(email: str, *, now_fn: Callable[[], datetime] = utcnow) -> int:
    """Failed attempts for one email inside the rolling window."""
    cutoff = now_fn() - LOCKOUT_WINDOW
    return (
        db.session.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.email == normalize(email),
                LoginAttempt.success.is_(False),
                LoginAttempt.attempted_at > cutoff,
            )
        )
        or 0
    )


def is_locked(email: str, *, now_fn: Callable[[], datetime] = utcnow) -> bool:
    return failure_count(email, now_fn=now_fn) >= LOCKOUT_LIMIT


def record_failure(email: str, *, now_fn: Callable[[], datetime] = utcnow) -> None:
    """Insert one failed attempt; self-committing so login stays simple."""
    db.session.add(LoginAttempt(email=normalize(email), attempted_at=now_fn(), success=False))
    db.session.commit()


def clear_failures(email: str) -> None:
    """Reset on full success (incl. the 2FA step); self-committing."""
    db.session.execute(delete(LoginAttempt).where(LoginAttempt.email == normalize(email)))
    db.session.commit()


def prune_old_attempts(*, now_fn: Callable[[], datetime] = utcnow) -> int:
    """Ticker-chore body: drop rows older than PRUNE_AFTER. Idempotent."""
    result = db.session.execute(
        delete(LoginAttempt).where(LoginAttempt.attempted_at < now_fn() - PRUNE_AFTER)
    )
    db.session.commit()
    return result.rowcount or 0
