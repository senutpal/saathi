"""Read-side event queries: IST day agenda and the month-grid provider for P12."""

from __future__ import annotations

import calendar
from datetime import date, datetime

from sqlalchemy import select

from ..extensions import db
from ..models import Event
from ..utils import ist_day_bounds_utc, utc_to_ist_wall


def day_events(user_id: int, day: date) -> list[Event]:
    """Events falling inside the local calendar day [00:00, next 00:00)."""
    lo, hi = ist_day_bounds_utc(day)
    return list(
        db.session.scalars(
            select(Event)
            .where(
                Event.user_id == user_id,
                Event.event_at >= lo,
                Event.event_at < hi,
                Event.status != "cancelled",
            )
            .order_by(Event.event_at)
        )
    )


def month_grid(user_id: int, year: int, month: int) -> dict:
    """Monday-first weeks of 7 dates plus events bucketed by local ISO date.

    Pure provider (no template coupling): P12's calendar page renders it as-is.
    """
    weeks: list[list[date]] = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    lo, _ = ist_day_bounds_utc(weeks[0][0])
    _, hi = ist_day_bounds_utc(weeks[-1][-1])
    rows = db.session.scalars(
        select(Event)
        .where(
            Event.user_id == user_id,
            Event.event_at >= lo,
            Event.event_at < hi,
            Event.status != "cancelled",
        )
        .order_by(Event.event_at)
    )
    by_date: dict[str, list[Event]] = {}
    for event in rows:
        key = utc_to_ist_wall(event.event_at).date().isoformat()
        by_date.setdefault(key, []).append(event)
    return {"weeks": weeks, "by_date": by_date}


def parse_iso_day(raw: str) -> date | None:
    """Strict YYYY-MM-DD parser; anything else is a 404-worthy input."""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None
