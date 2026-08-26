"""Shared helpers: safe redirects, owned fetches, audit rows, TZ boundaries."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import abort, current_app, url_for
from flask_login import current_user

from .extensions import db
from .models import ActivityLog
from .models.base import utcnow

PHONE_CHARS = re.compile(r"[0-9+()\-\s.]")


def local_zone() -> ZoneInfo:
    """The display/input timezone (config TIMEZONE); storage stays naive UTC."""
    return ZoneInfo(current_app.config["TIMEZONE"])


def ist_to_utc_naive(wall: datetime) -> datetime:
    """Local wall-clock datetime -> naive UTC coordinate (the input boundary)."""
    return wall.replace(tzinfo=local_zone()).astimezone(UTC).replace(tzinfo=None)


def utc_to_ist_wall(dt: datetime) -> datetime:
    """Naive UTC coordinate -> local wall-clock (form prefill boundary)."""
    return dt.replace(tzinfo=UTC).astimezone(local_zone()).replace(tzinfo=None)


def ist_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """A local calendar day [00:00, next 00:00) as naive UTC range endpoints."""
    zone = local_zone()
    lo = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC).replace(tzinfo=None)
    hi = (
        datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    return lo, hi


def ist_format(dt_naive_utc: datetime) -> str:
    """Render stored naive UTC as a local display string with explicit zone."""
    aware = dt_naive_utc.replace(tzinfo=UTC).astimezone(local_zone())
    return f"{aware:%d %b %Y, %I:%M %p} {aware:%Z}"


def ist_today() -> date:
    """The local calendar date for 'today' — never date.today() (machine TZ)."""
    return utc_to_ist_wall(utcnow()).date()


def month_bounds(raw: str | None) -> tuple[date, date]:
    """[first_day, day_after_last) bounds for 'YYYY-MM' or the current month.

    Raises 404 on malformed input so bad ?month= links fail loudly.
    """
    import calendar

    today = ist_today()
    if raw:
        try:
            year_str, month_str = raw.split("-")
            first = date(int(year_str), int(month_str), 1)
        except ValueError:
            abort(404)
    else:
        first = today.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, last + timedelta(days=1)


def external_url(endpoint: str, **values: object) -> str:
    """Absolute site URL for an endpoint; configured APP_URL wins over Host.

    Behind proxies url_for(_external=True) reflects the request Host, so the
    configured APP_URL (B17 pitfall P8) is preferred when present.
    """
    path = url_for(endpoint, **values)
    base = current_app.config.get("APP_URL", "").rstrip("/")
    return f"{base}{path}" if base else url_for(endpoint, **values, _external=True)


def safe_next(target: str | None) -> str:
    """Return target only if it is a site-relative path ('/x'), else ''.

    Rejects protocol-relative '//host', backslash variants and absolute URLs,
    so a forged ?next= can never bounce a login off-site.
    """
    if not target or "\\" in target:
        return ""
    parts = urlsplit(target)
    is_relative = parts.scheme == "" and parts.netloc == ""
    starts_safe = target.startswith("/") and not target.startswith("//")
    if is_relative and starts_safe:
        return target
    return ""


def get_own_or_404(model: type[db.Model], obj_id: int) -> db.Model:
    """MANDATORY for any fetch of another-user-reachable resource.

    The owner filter rides inside the fetch, so a foreign id is
    indistinguishable from a missing one (404, never 403 — no existence leak).
    """
    obj = model.query.filter_by(id=obj_id, user_id=current_user.id).first()
    if obj is None:
        abort(404)
    return obj


def csv_safe(cell: str) -> str:
    """Prefix-quote spreadsheet formula triggers (OWASP CSV-injection guidance)."""
    if cell.startswith(("=", "+", "-", "@", "\t")):
        return "'" + cell
    return cell


def log_action(
    user_id: int,
    activity_type: str,
    title: str,
    details: str | None = None,
    event_id: int | None = None,
) -> None:
    """Queue an ActivityLog row (ADR-015 shape) on the current transaction; caller commits.

    Same-transaction rule (B08 pitfall #8): an audit row must live or die with
    the mutation it describes. Verbs come from the B08 VOCAB set.
    """
    db.session.add(
        ActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            title=title[:120],
            details=details,
            event_id=event_id,
        )
    )
