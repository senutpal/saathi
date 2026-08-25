"""History routes: day-grouped activity timeline plus CSV export of the same filter."""

from __future__ import annotations

import csv
import io
from datetime import timedelta

from flask import Blueprint, Response, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from sqlalchemy import Select, select

from ..extensions import db
from ..models import ActivityLog
from ..models.base import utcnow
from ..services.notes import like_escape
from ..utils import ist_format, utc_to_ist_wall

bp = Blueprint("history", __name__, url_prefix="/history")

PAGE_SIZE = 25

# Every option is a pure startswith match on activity_type, so the filter
# needs no extra query semantics; auth/profile/CV rows are single verbs.
FILTER_FAMILIES: list[tuple[str, str]] = [
    ("", "All activity"),
    ("event_", "Reminders"),
    ("note_", "Notes"),
    ("file_", "Files"),
    ("web_search_", "Web search"),
    ("notifications_", "Notifications"),
    ("login", "Sign-ins"),
    ("cv_export", "CV exports"),
    ("profile_updated", "Profile edits"),
]


def _filtered(user_id: int, prefix: str) -> Select[tuple[ActivityLog]]:
    stmt = select(ActivityLog).where(ActivityLog.user_id == user_id)
    if prefix:
        # like_escape handles wildcards; autoescape=True here would re-escape
        # the backslashes it just inserted (B08 sketch double-escape bug).
        stmt = stmt.where(ActivityLog.activity_type.startswith(like_escape(prefix), escape="\\"))
    return stmt.order_by(ActivityLog.occurred_at.desc())


def _day_groups(items: list[ActivityLog]) -> list[tuple[str, list[tuple[ActivityLog, str]]]]:
    """Newest-first rows grouped under IST calendar-day headings.

    Each entry carries its local ISO date so templates can deep-link
    reminder rows to the day agenda without extra queries.
    """
    today = utc_to_ist_wall(utcnow()).date()
    labels = {today: "Today", today - timedelta(days=1): "Yesterday"}
    groups: list[tuple[str, list[tuple[ActivityLog, str]]]] = []
    for row in items:
        day = utc_to_ist_wall(row.occurred_at).date()
        label = labels.get(day, f"{day:%d %b %Y}")
        if not groups or groups[-1][0] != label:
            groups.append((label, []))
        groups[-1][1].append((row, day.isoformat()))
    return groups


@bp.get("")
@login_required
def page() -> str:
    prefix = request.args.get("type", "").strip()[:30]
    pg = db.paginate(
        _filtered(current_user.id, prefix),
        page=max(request.args.get("page", 1, type=int), 1),
        per_page=PAGE_SIZE,
        error_out=False,
    )
    return render_template(
        "history.html",
        pg=pg,
        groups=_day_groups(list(pg.items)),
        prefix=prefix,
        families=FILTER_FAMILIES,
    )


def _csv_safe(cell: str) -> str:
    """Prefix-quote spreadsheet formula triggers (OWASP CSV-injection guidance)."""
    if cell.startswith(("=", "+", "-", "@", "\t")):
        return "'" + cell
    return cell


@bp.get("/export.csv")
@login_required
def export_csv() -> ResponseReturnValue:
    prefix = request.args.get("type", "").strip()[:30]
    rows = db.session.scalars(_filtered(current_user.id, prefix)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["occurred_at", "activity_type", "title", "details"])
    for row in rows:
        writer.writerow(
            [
                ist_format(row.occurred_at),
                _csv_safe(row.activity_type),
                _csv_safe(row.title),
                _csv_safe(row.details or ""),
            ]
        )
    stamp = utc_to_ist_wall(utcnow()).date()
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=history-{stamp:%Y%m%d}.csv"},
    )
