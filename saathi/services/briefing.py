"""Daily-briefing aggregator: one dict per authed home render.

Every card degrades independently — a failing aggregator logs and yields
its safe default instead of killing the dashboard.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from flask import current_app
from sqlalchemy import func, select

from ..extensions import db
from ..models import ActivityLog, Event, Note, Notification
from ..models.base import utcnow
from ..utils import utc_to_ist_wall
from .agenda import day_events
from .daily import habit_overview as _fetch_habit_overview
from .daily import mood_summary as _fetch_mood_summary
from .daily import upcoming_birthdays as _fetch_upcoming_birthdays
from .search import get_weather

log = logging.getLogger(__name__)

GREETINGS = ((12, "Good morning"), (17, "Good afternoon"))


def _greeting(now_utc_naive: datetime) -> str:
    hour = utc_to_ist_wall(now_utc_naive).hour
    for edge, text in GREETINGS:
        if hour < edge:
            return text
    return "Good evening"


def _overdue_count(user_id: int, now_utc_naive: datetime) -> int:
    """Scheduled reminders whose time has passed but the ticker hasn't claimed."""
    return (
        db.session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.user_id == user_id,
                Event.status == "scheduled",
                Event.event_at < now_utc_naive,
            )
        )
        or 0
    )


def _unread_count(user_id: int) -> int:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


def _recent_notes(user_id: int, limit: int = 3) -> list[Note]:
    return list(
        db.session.scalars(
            select(Note)
            .where(Note.user_id == user_id, Note.deleted_at.is_(None))
            .order_by(Note.updated_at.desc(), Note.id.desc())
            .limit(limit)
        )
    )


def _upcoming_birthdays(user_id: int, today: date) -> list[Any]:
    """Contacts query for upcoming birthdays inside window."""
    if "contacts" not in db.metadata.tables:
        return []
    return list(_fetch_upcoming_birthdays(user_id, today))


HABIT_CARD_LIMIT = 5


def _habit_rows(user_id: int, today: date) -> list[dict]:
    if "habits" not in db.metadata.tables:
        return []
    return _fetch_habit_overview(user_id, today)[:HABIT_CARD_LIMIT]


def _mood_card(user_id: int) -> dict:
    """Trailing-14-day scores + average; one query, empty-safe."""
    if "moods" not in db.metadata.tables:
        return {"scores": [], "avg": None}
    scores = _fetch_mood_summary(user_id)
    avg = round(sum(scores) / len(scores), 1) if scores else None
    return {"scores": scores, "avg": avg}


def _weather() -> dict | None:
    city = current_app.config.get("WEATHER_CITY", "")
    if not city:
        return None
    return get_weather(city)


def _on_this_day(user_id: int, now_utc_naive: datetime) -> ActivityLog | None:
    """Same local month-day from previous years — cheap delight row."""
    wall = utc_to_ist_wall(now_utc_naive)
    return db.session.scalar(
        select(ActivityLog)
        .where(
            ActivityLog.user_id == user_id,
            func.strftime("%m-%d", ActivityLog.occurred_at) == f"{wall:%m-%d}",
            func.strftime("%Y", ActivityLog.occurred_at) < str(wall.year),
        )
        .order_by(ActivityLog.occurred_at.desc())
        .limit(1)
    )


def _safe(label: str, fn: Callable[[], Any], default: Any) -> Any:
    try:
        return fn()
    except Exception:
        log.exception("briefing card %s degraded", label)
        return default


def build_briefing(user_id: int, *, now_fn: Callable[[], datetime] = utcnow) -> dict:
    """Aggregate every dashboard card in one pass; never raises."""
    now = now_fn()
    today = utc_to_ist_wall(now).date()
    return {
        "today": today,
        "greeting": _safe("greeting", lambda: _greeting(now), "Hello"),
        "today_events": _safe("today_events", lambda: day_events(user_id, today), []),
        "overdue_count": _safe("overdue", lambda: _overdue_count(user_id, now), 0),
        "unread_count": _safe("unread", lambda: _unread_count(user_id), 0),
        "birthdays": _safe("birthdays", lambda: _upcoming_birthdays(user_id, today), []),
        "habit_rows": _safe("habit_rows", lambda: _habit_rows(user_id, today), []),
        "mood_card": _safe("mood_card", lambda: _mood_card(user_id), {"scores": [], "avg": None}),
        "recent_notes": _safe("recent_notes", lambda: _recent_notes(user_id), []),
        "weather": _safe("weather", _weather, None),
        "on_this_day": _safe("on_this_day", lambda: _on_this_day(user_id, now), None),
        "has_habits": "habits" in db.metadata.tables,
        "has_moods": "moods" in db.metadata.tables,
        "has_contacts": "contacts" in db.metadata.tables,
    }
