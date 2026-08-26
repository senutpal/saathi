"""Calendar routes: month grid page plus the token-authed ICS subscribe feed.

The blueprint carries no login gate: /calendar is per-route @login_required
while /calendar.ics authenticates by bearer token (calendar apps have no
session). Bad token == missing token == feature-off -> uniform 404.
"""

from __future__ import annotations

import hmac
from datetime import timedelta

import sqlalchemy as sa
from flask import Blueprint, Response, abort, render_template, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import User
from ..services.agenda import build_calendar
from ..services.ics import events_to_ical
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


def _user_for_token(given: str) -> User | None:
    """Constant-time comparison over issued tokens; linear scan at course scale.

    Upgrade path (B14 §5.6): store sha256(token) indexed and look up by digest.
    """
    if not given:
        return None
    rows = db.session.scalars(sa.select(User).where(User.ics_token.is_not(None)))
    for user in rows:
        if hmac.compare_digest(user.ics_token or "", given):
            return user
    return None


@bp.get("/calendar.ics")
def ics() -> Response:
    user = _user_for_token(request.args.get("token", ""))
    if user is None:
        abort(404)
    response = Response(events_to_ical(user), mimetype="text/calendar")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Disposition"] = 'inline; filename="saathi.ics"'
    return response
