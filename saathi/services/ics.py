"""RFC 5545 feed builder for the per-user ICS subscription.

Recurrences are materialized rows, so RRULE is never emitted —
subscribers would double-book every repeat. Naive-UTC storage re-attaches
timezone.utc directly: RFC 5545 Z-form is a relabeling, not a conversion.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import timezone
UTC = timezone.utc, datetime, timedelta

from icalendar import Alarm, Calendar
from icalendar import Event as IcalEvent
from sqlalchemy import select

from ..extensions import db
from ..models import Event, User

PRODID = "-//Saathi//Calendar 1.0//EN"


def new_token() -> str:
    """~192-bit URL-safe bearer secret for the subscribe URL."""
    return secrets.token_urlsafe(24)


def _aware_utcnow() -> datetime:
    return datetime.now(UTC)


def events_to_ical(user: User, *, now_fn: Callable[[], datetime] = _aware_utcnow) -> bytes:
    """Serialize every non-cancelled event into a complete VCALENDAR."""
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", f"{user.username} · Saathi")
    stamp = now_fn()
    rows = db.session.scalars(
        select(Event)
        .where(Event.user_id == user.id, Event.status != "cancelled")
        .order_by(Event.event_at)
    ).all()
    for row in rows:
        start = row.event_at.replace(tzinfo=UTC)
        component = IcalEvent()
        component.add("uid", f"event-{row.id}@saathi")
        component.add("dtstamp", stamp)
        component.add("dtstart", start)
        component.add("dtend", start)
        component.add("summary", row.title)
        if row.description:
            component.add("description", row.description[:280])
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("trigger", timedelta(minutes=-(row.alert_lead_minutes or 10)))
        alarm.add("description", row.title)
        component.add_component(alarm)
        cal.add_component(component)
    return cal.to_ical()
