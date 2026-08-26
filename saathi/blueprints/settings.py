"""Settings routes: personal integrations — ICS subscribe link (digest joins in S6)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from ..extensions import db
from ..services.ics import new_token
from ..utils import external_url, log_action

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.get("")
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


@bp.post("/calendar-token/regenerate")
@login_required
def regenerate() -> ResponseReturnValue:
    current_user.ics_token = new_token()
    log_action(current_user.id, "settings_updated", "Calendar feed link regenerated")
    db.session.commit()
    flash("New calendar link generated; the old link no longer works.")
    return redirect(url_for("settings.index"))
