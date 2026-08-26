"""Calendar routes: month grid page (the ICS feed lands here in S3)."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from ..services.agenda import build_calendar
from ..utils import ist_today, month_bounds

bp = Blueprint("calendar", __name__)


@bp.get("/calendar")
@login_required
def month_view() -> str:
    first, first_of_next = month_bounds(request.args.get("month"))
    grid = build_calendar(current_user.id, first.year, first.month)
    return render_template(
        "calendar/month.html",
        grid=grid,
        cur_label=f"{first:%B %Y}",
        prev_month=(first - timedelta(days=1)).strftime("%Y-%m"),
        next_month=first_of_next.strftime("%Y-%m"),
        today_iso=ist_today().isoformat(),
    )
