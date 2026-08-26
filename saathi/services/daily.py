"""Daily life aggregations: birthdays, habit grids, weekly digest, day chores.

Pure-Python date math by design (B17 §2): SQL ``strftime BETWEEN`` windows
invert across Dec→Jan and silently drop Feb-29 in common years; per-user
contact counts are tiny, so clarity wins.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from flask import current_app, render_template
from sqlalchemy import func, select

from ..extensions import db
from ..models import CapsuleMessage, Contact, Event, Habit, HabitLog, Mood, Notification, User
from ..models.base import utcnow
from ..utils import ist_day_bounds_utc, ist_to_utc_naive, ist_today, utc_to_ist_wall
from .lockout import prune_old_attempts
from .mailer import send_email

log = logging.getLogger(__name__)

_last_sync_day: date | None = None
_last_chore_day: date | None = None

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


DIGEST_STREAK_LIMIT = 5


def _overdue_count(user_id: int, now: datetime) -> int:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.user_id == user_id,
                Event.status == "scheduled",
                Event.event_at < now,
            )
        )
        or 0
    )


def digest_context(user: User, *, now_fn: Callable[[], datetime] = utcnow) -> dict:
    """Everything the weekly email shows; same queries as the preview page."""
    now = now_fn()
    today = utc_to_ist_wall(now).date()
    lo, _ = ist_day_bounds_utc(today)
    __, hi = ist_day_bounds_utc(today + timedelta(days=7))
    events = list(
        db.session.scalars(
            select(Event)
            .where(
                Event.user_id == user.id,
                Event.event_at >= lo,
                Event.event_at < hi,
                Event.status != "cancelled",
            )
            .order_by(Event.event_at)
        )
    )
    streaks = sorted(
        (
            (row["habit"].name, row["current"])
            for row in habit_overview(user.id, today=today)
            if row["current"] > 0
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )[:DIGEST_STREAK_LIMIT]
    return {
        "username": user.username,
        "range_label": f"{today:%d %b} – {today + timedelta(days=6):%d %b %Y}",
        "events": events,
        "overdue": _overdue_count(user.id, now),
        "birthdays": upcoming_birthdays(user.id, today, days=7),
        "streaks": streaks,
    }


def send_digest(user: User, *, now_fn: Callable[[], datetime] = utcnow) -> int:
    """One Monday email per opted-in user; 1 sent, 0 skipped-or-failed.

    The digest_last_sent_at column is the idempotency guard, so a failed SMTP
    attempt never marks the week done — a restarted process retries the same
    Monday. A missed Monday is simply skipped (B06 misfire-cap philosophy).
    """
    today = utc_to_ist_wall(now_fn()).date()
    already = user.digest_last_sent_at is not None and (user.digest_last_sent_at.date() == today)
    if today.weekday() != 0 or already:
        return 0
    ctx = digest_context(user, now_fn=now_fn)
    html = render_template("emails/digest.html", **ctx)
    plain_lines = [f"Saathi — your week of {today:%d %b}", ""]
    plain_lines += [
        f"{utc_to_ist_wall(ev.event_at):%a %d %b %H:%M} IST  {ev.title}" for ev in ctx["events"]
    ]
    if ctx["overdue"]:
        plain_lines.append(f"{ctx['overdue']} reminder(s) overdue — review them in Saathi.")
    if not ctx["events"]:
        plain_lines.append("Nothing scheduled — enjoy the calm.")
    ok = send_email(
        user.email,
        f"Saathi — your week of {today:%d %b}",
        html,
        "\n".join(plain_lines),
    )
    if ok:
        user.digest_last_sent_at = now_fn()
        db.session.commit()
    return int(ok)


def open_due_capsules(*, now_fn: Callable[[], datetime] = utcnow) -> int:
    """Flip sealed->opened past open_at; one notification per newly opened.

    The status filter makes reruns no-ops, so the per-process chore memo can
    reset freely (B15 pitfall 7). Reveal granularity is daily by design.
    """
    due = list(
        db.session.scalars(
            select(CapsuleMessage).where(
                CapsuleMessage.status == "sealed",
                CapsuleMessage.open_at <= now_fn(),
            )
        )
    )
    for capsule in due:
        capsule.status = "opened"
        sealed_on = f"{capsule.created_at:%d %b %Y}"
        db.session.add(
            Notification(
                user_id=capsule.user_id,
                event_id=None,
                title="A message from your past self",
                body=f"You sealed '{capsule.title[:100]}' on {sealed_on}. It's ready.",
            )
        )
    if due:
        db.session.commit()
    return len(due)


def maybe_daily_chores(*, now_fn: Callable[[], datetime] = utcnow) -> dict:
    """At-most-once-per-process-day maintenance riding the ticker loop.

    The memo resets on restart by design, so every chore body must be
    idempotent on its own state (digest date-guard, capsule status filter).
    """
    global _last_chore_day
    day = utc_to_ist_wall(now_fn()).date()
    if _last_chore_day == day:
        return {}
    _last_chore_day = day
    users = db.session.scalars(select(User).where(User.digest_enabled.is_(True))).all()
    return {
        "digests": sum(send_digest(user, now_fn=now_fn) for user in users),
        "capsules_opened": open_due_capsules(now_fn=now_fn),
        "login_rows_pruned": prune_old_attempts(now_fn=now_fn),
    }
