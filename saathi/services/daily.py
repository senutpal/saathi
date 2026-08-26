"""Daily life aggregations: upcoming birthdays plus their optional event sync.

Pure-Python date math by design (B17 §2): SQL ``strftime BETWEEN`` windows
invert across Dec→Jan and silently drop Feb-29 in common years; per-user
contact counts are tiny, so clarity wins.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import Contact, Event, Habit, HabitLog, Mood
from ..utils import ist_to_utc_naive, ist_today

log = logging.getLogger(__name__)

_last_sync_day: date | None = None

GRID_DAYS = 60

# Literal Tailwind classes keyed by palette KEY — interpolated color strings
# never survive JIT purging (B17 pitfall P6); muted/ring stay semantic tokens.
GRID_FILL: dict[str | None, str] = {
    "sky": "bg-sky-500",
    "emerald": "bg-emerald-500",
    "amber": "bg-amber-500",
    "rose": "bg-rose-500",
    "violet": "bg-violet-500",
}
GRID_EMPTY = "bg-muted"


def habit_streaks(logged: set[date], today: date, window: int = GRID_DAYS) -> tuple[int, int]:
    """(current, longest) done-day run lengths; day arithmetic ignores months.

    A Python loop beats SQL gaps-and-islands here: window functions through
    SQLAlchemy mean text() fragments and dialect-coupled tests for zero gain
    at <=60 rows (B17 §3.1).
    """
    current = 0
    probe = today if today in logged else today - timedelta(days=1)
    while probe in logged:
        current += 1
        probe -= timedelta(days=1)

    longest = run = 0
    for offset in range(window):
        day = today - timedelta(days=offset)
        run = run + 1 if day in logged else 0
        longest = max(longest, run)
    return current, longest


def habit_overview(user_id: int, today: date | None = None) -> list[dict]:
    """Per-habit grid/streak rows in two queries total (budget law)."""
    day = today or ist_today()
    habits = list(
        db.session.scalars(select(Habit).where(Habit.user_id == user_id).order_by(Habit.id))
    )
    if not habits:
        return []
    since = day - timedelta(days=GRID_DAYS - 1)
    logged_pairs = db.session.execute(
        select(HabitLog.habit_id, HabitLog.log_date)
        .join(Habit, HabitLog.habit_id == Habit.id)
        .where(Habit.user_id == user_id, HabitLog.log_date >= since)
    ).all()
    by_habit: dict[int, set[date]] = {}
    for habit_id, logged_on in logged_pairs:
        by_habit.setdefault(habit_id, set()).add(logged_on)

    days = [day - timedelta(days=offset) for offset in range(GRID_DAYS - 1, -1, -1)]
    rows = []
    for habit in habits:
        logged = by_habit.get(habit.id, set())
        current, longest = habit_streaks(logged, day)
        rows.append(
            {
                "habit": habit,
                "logged": logged,
                "days": days,
                "current": current,
                "longest": longest,
            }
        )
    return rows


def _anniv_in_window(dob: date, today: date, days: int) -> date | None:
    """Next occurrence of dob within [today, today+days]; Feb-29 celebrates Feb-28."""
    for year in (today.year, today.year + 1):
        try:
            cand = dob.replace(year=year)
        except ValueError:
            cand = date(year, 2, 28)
        if today <= cand <= today + timedelta(days=days):
            return cand
    return None


def upcoming_birthdays(
    user_id: int, today: date, *, days: int = 7
) -> list[tuple[Contact, date, int]]:
    """(contact, anniversary, turning_age) tuples sorted by nearest celebration."""
    rows = db.session.scalars(
        select(Contact).where(Contact.user_id == user_id, Contact.dob.is_not(None))
    ).all()
    hits: list[tuple[Contact, date, int]] = []
    for contact in rows:
        cand = _anniv_in_window(contact.dob, today, days)
        if cand is not None:
            hits.append((contact, cand, cand.year - contact.dob.year))
    hits.sort(key=lambda hit: hit[1])
    return hits


def _next_anniversary(dob: date, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            cand = dob.replace(year=year)
        except ValueError:
            cand = date(year, 2, 28)
        if cand >= today:
            return cand
    return None


def mood_summary(user_id: int, *, days: int = 14, today: date | None = None) -> list[int]:
    """Scores oldest→newest over the trailing window; one query."""
    day = today or ist_today()
    since = day - timedelta(days=days - 1)
    return list(
        db.session.scalars(
            select(Mood.score)
            .where(Mood.user_id == user_id, Mood.mood_date >= since)
            .order_by(Mood.mood_date, Mood.id)
        )
    )


def maybe_sync_birthday_events(today: date | None = None) -> int:
    """Create one yearly 'Birthday: <name>' event per dated contact, once/day.

    Runs from the ticker cycle (config BIRTHDAYS_AS_EVENTS, default OFF).
    The title-prefix existence probe is the mandatory dedupe guard (B17 P2):
    without it every scan would spawn duplicate yearly events. Returns how
    many events were created.
    """
    global _last_sync_day
    day = today or ist_today()
    if _last_sync_day == day:
        return 0
    _last_sync_day = day
    if not current_app.config.get("BIRTHDAYS_AS_EVENTS"):
        return 0

    contacts = db.session.execute(
        select(Contact.user_id, Contact.name, Contact.dob).where(Contact.dob.is_not(None))
    ).all()
    if not contacts:
        return 0
    known: dict[int, set[str]] = {}
    for user_id, title in db.session.execute(
        select(Event.user_id, Event.title).where(
            Event.status != "cancelled", Event.title.like("Birthday: %")
        )
    ):
        known.setdefault(user_id, set()).add(title)

    created = 0
    for user_id, name, dob in contacts:
        title = f"Birthday: {name}"[:200]
        if title in known.get(user_id, set()):
            continue
        anniv = _next_anniversary(dob, day)
        if anniv is None:
            continue
        at_nine_local = ist_to_utc_naive(datetime.combine(anniv, time(9, 0)))
        db.session.add(
            Event(
                user_id=user_id,
                title=title,
                event_at=at_nine_local,
                repeat_rule="yearly",
                alert_lead_minutes=60,
            )
        )
        created += 1
    db.session.commit()
    log.info("birthday events created=%d", created)
    return created
