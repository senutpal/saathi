"""Settings routes: personal integrations — ICS subscribe link and weekly digest."""

from __future__ import annotations

from flask import Blueprint, Response, flash, redirect, render_template, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from ..extensions import db
from ..models.base import utcnow
from ..services.daily import digest_context
from ..services.ics import new_token
from ..utils import external_url, log_action

bp = Blueprint("settings", __name__)


@bp.get("/settings")
@login_required
def index() -> str:
    # lazy mint: the token exists only once the owner first opens this page
    if not current_user.ics_token:
        current_user.ics_token = new_token()
        db.session.commit()
    return render_template(
        "settings/index.html",
        ics_url=external_url("calendar.ics", token=current_user.ics_token),
    )


@bp.post("/settings/calendar-token/regenerate")
@login_required
def regenerate() -> ResponseReturnValue:
    current_user.ics_token = new_token()
    log_action(current_user.id, "settings_updated", "Calendar feed link regenerated")
    db.session.commit()
    flash("New calendar link generated; the old link no longer works.")
    return redirect(url_for("settings.index"))


@bp.post("/settings/digest-toggle")
@login_required
def digest_toggle() -> ResponseReturnValue:
    current_user.digest_enabled = not current_user.digest_enabled
    detail = "Weekly digest enabled" if current_user.digest_enabled else "Weekly digest disabled"
    log_action(current_user.id, "settings_updated", detail)
    db.session.commit()
    flash(detail + ".")
    return redirect(url_for("settings.index"))


@bp.get("/digest/preview")
@login_required
def digest_preview() -> Response:
    """The exact email document, standalone — report-screenshot friendly."""
    ctx = digest_context(current_user, now_fn=utcnow)
    return Response(render_template("emails/digest.html", **ctx), mimetype="text/html")
