"""Reminder ticker engine: idempotent claim-scan over due events.

Design (ADR-003): SQLite is the durable queue — a single daemon thread (or the
cron-hosted /tick endpoint) repeatedly claims due rows with a conditional
UPDATE whose rowcount is the race winner's proof. Restart catch-up and
exactly-once firing fall out of that claim for free.
"""

from __future__ import annotations

import atexit
import calendar
import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from flask import Flask, current_app
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from ..extensions import db
from ..models import ActivityLog, Event, Notification
from ..models.base import utcnow
from ..utils import ist_format
from .daily import maybe_sync_birthday_events
from .mailer import enqueue_email

log = logging.getLogger("saathi.ticker")

_stop = threading.Event()
_started = False

_LOCK_RETRY_PAUSE = 0.05
_MAX_LOCK_RETRIES = 3


def _add_months(dt: datetime, months: int = 1) -> datetime:
    """Calendar month arithmetic clamped to month end: Jan 31 -> Feb 28."""
    total = dt.month - 1 + months
    year = dt.year + total // 12
    month = total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def next_occurrence(dt: datetime, rule: str) -> datetime:
    if rule == "daily":
        return dt + timedelta(days=1)
    if rule == "weekly":
        return dt + timedelta(weeks=1)
    if rule == "monthly":
        return _add_months(dt)
    raise ValueError(f"unsupported repeat_rule {rule!r}")


def scan_and_fire(*, now_fn: Callable[[], datetime] = utcnow, limit: int = 50) -> int:
    """Claim every due scheduled event exactly once; return how many were claimed.

    Concurrency-safe from both the ticker thread and /tick: each candidate is
    claimed by UPDATE ... WHERE status='scheduled' inside its own short
    transaction — SQLite's single-writer lock serializes contenders and
    rowcount==1 tells the loser to walk away without notifying. A contender
    whose read snapshot went stale gets BUSY_SNAPSHOT (busy_timeout does not
    apply there), so lock errors are retried from a fresh snapshot.
    """
    now = now_fn()
    grace = current_app.config["MISFIRE_GRACE"]
    late_threshold = current_app.config["LATE_THRESHOLD"]
    fired = 0
    stalls = 0
    emailed_ids: list[int] = []
    while True:
        try:
            with db.session.begin():
                found, won, notification_id = _claim_one(now, grace, late_threshold, limit)
        except OperationalError:
            db.session.rollback()
            stalls += 1
            if stalls > _MAX_LOCK_RETRIES:
                raise
            time.sleep(_LOCK_RETRY_PAUSE)
            continue
        stalls = 0
        if not found:
            break
        if won:
            fired += 1
            if notification_id is not None:
                emailed_ids.append(notification_id)
    if emailed_ids:
        # ids only exist once their insert committed, so this is always post-commit
        try:
            enqueue_email(current_app._get_current_object(), emailed_ids)
        except Exception:  # noqa: BLE001 — never break the tick over email
            log.exception("email enqueue failed")
    try:
        maybe_sync_birthday_events()
    except Exception:  # noqa: BLE001 — maintenance must never break event claiming
        log.exception("birthday sync failed")
    return fired


def _claim_one(
    now: datetime, grace: timedelta, late_threshold: timedelta, limit: int
) -> tuple[bool, int, int | None]:
    """Process one due candidate; returns (candidate_found, claimed_by_us, notification_id)."""
    event = db.session.scalar(
        select(Event)
        .where(Event.status == "scheduled", Event.event_at <= now)
        .order_by(Event.event_at)
        .limit(limit)
    )
    if event is None:
        return False, 0, None
    delta = now - event.event_at
    if delta > grace:
        target_status = "missed"
    elif delta > late_threshold:
        target_status = "fired_late"
    else:
        target_status = "fired"
    claim = db.session.execute(
        update(Event)
        .where(Event.id == event.id, Event.status == "scheduled")
        .values(status=target_status, fired_at=now)
    )
    if claim.rowcount != 1:
        return True, 0, None  # lost the race to a concurrent scanner; keep scanning
    notification_id: int | None = None
    if target_status != "missed":
        notification = Notification(
            user_id=event.user_id,
            event_id=event.id,
            title=event.title,
            body=f"Due {ist_format(event.event_at)}",
        )
        db.session.add(notification)
        db.session.add(
            ActivityLog(
                user_id=event.user_id,
                event_id=event.id,
                activity_type="event_fired",
                title=event.title[:120],
                details=target_status,
            )
        )
        db.session.flush()
        notification_id = notification.id
    if event.repeat_rule != "none":
        db.session.add(
            Event(
                user_id=event.user_id,
                title=event.title,
                description=event.description,
                event_at=next_occurrence(event.event_at, event.repeat_rule),
                repeat_rule=event.repeat_rule,
                alert_lead_minutes=event.alert_lead_minutes,
            )
        )
    return True, 1, notification_id


def _loop(app: Flask, interval: float, now_fn: Callable[[], datetime]) -> None:
    while not _stop.wait(interval):
        try:
            # Fresh context per scan: teardown rolls back any half-done state.
            with app.app_context():
                fired = scan_and_fire(now_fn=now_fn)
            if fired:
                log.info("tick fired=%d", fired)
        except Exception:  # noqa: BLE001 — a failed scan must never kill the thread
            log.exception("tick failed; retrying next interval")


def start_ticker(app: Flask, *, now_fn: Callable[[], datetime] = utcnow) -> bool:
    """Start the daemon ticker once per process; returns whether it started."""
    global _started
    if _started or app.config.get("TESTING") or not app.config["SCHEDULER_ENABLED"]:
        return False
    _started = True
    _stop.clear()
    threading.Thread(
        target=_loop,
        args=(app, app.config["TICK_SECONDS"], now_fn),
        name="events-ticker",
        daemon=True,
    ).start()
    atexit.register(stop_ticker)
    log.info("ticker started (every %ss)", app.config["TICK_SECONDS"])
    return True


def stop_ticker() -> None:
    _stop.set()


def reset_for_tests() -> None:
    """Reset module-singleton state so tests can start/stop tickers freely."""
    global _started
    stop_ticker()
    _started = False
