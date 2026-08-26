"""Read-side event queries: IST day agenda and the month-grid provider for P12."""

from __future__ import annotations

import calendar
from datetime import date, datetime

from sqlalchemy import select

from ..extensions import db
from ..models import Contact, Event, Habit, HabitLog
from ..utils import ist_day_bounds_utc, ist_today, utc_to_ist_wall


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


def _event_chip(event: Event) -> dict:
    wall = utc_to_ist_wall(event.event_at)
    return {"kind": "event", "label": f"{wall:%H:%M} {event.title}", "title": event.title}


def _birthday_chips(user_id: int, lo: date, hi: date) -> list[tuple[str, str]]:
    """(iso_day, name) for contact birthdays inside the displayed span.

    Same two-pass year scan + Feb-29 fallback as daily._anniv_in_window,
    widened from 'today+window' to an arbitrary month range.
    """
    contacts = db.session.scalars(
        select(Contact).where(Contact.user_id == user_id, Contact.dob.is_not(None))
    ).all()
    hits: list[tuple[str, str]] = []
    for contact in contacts:
        for year in range(lo.year, hi.year + 1):
            try:
                cand = contact.dob.replace(year=year)
            except ValueError:
                cand = date(year, 2, 28)
            if lo <= cand <= hi:
                hits.append((cand.isoformat(), contact.name))
                break
    return hits


def _habit_chips(user_id: int, lo: date, hi: date) -> list[tuple[str, str]]:
    return [
        (row.log_date.isoformat(), row.name)
        for row in db.session.execute(
            select(HabitLog.log_date, Habit.name)
            .join(Habit, HabitLog.habit_id == Habit.id)
            .where(Habit.user_id == user_id, HabitLog.log_date >= lo, HabitLog.log_date <= hi)
        ).all()
    ]


def build_calendar(user_id: int, year: int, month: int, *, today: date | None = None) -> dict:
    """Render-ready month grid: cell dicts + chips (events/birthdays/habits).

    Wraps the frozen P05 month_grid() contract; sibling overlays stay optional
    via metadata-table guards so pre-P11 databases contribute zero chips.
    """
    grid = month_grid(user_id, year, month)
    day0 = today or ist_today()
    weeks = [
        [
            {
                "date": day,
                "iso": day.isoformat(),
                "in_month": day.month == month,
                "is_today": day == day0,
            }
            for day in week
        ]
        for week in grid["weeks"]
    ]
    by_date: dict[str, list[dict]] = {
        iso: [_event_chip(event) for event in events] for iso, events in grid["by_date"].items()
    }
    lo, hi = grid["weeks"][0][0], grid["weeks"][-1][-1]
    if "contacts" in db.metadata.tables:
        for iso, name in _birthday_chips(user_id, lo, hi):
            by_date.setdefault(iso, []).append({"kind": "birthday", "label": name})
    if "habits" in db.metadata.tables:
        for iso, name in _habit_chips(user_id, lo, hi):
            by_date.setdefault(iso, []).append({"kind": "habit", "label": name})
    return {"weeks": weeks, "by_date": by_date}
