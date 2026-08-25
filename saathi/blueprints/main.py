import hmac

from flask import Blueprint, abort, current_app, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from ..extensions import csrf
from ..services.briefing import build_briefing
from ..services.scheduler import scan_and_fire

bp = Blueprint("main", __name__)


@bp.get("/")
@login_required
def index() -> str:
    return render_template("main/home.html", **build_briefing(current_user.id))


@bp.get("/dev/style")
def style() -> str:
    if current_app.config["SAATHI_ENV"] != "development":
        abort(404)
    return render_template("main/style.html")


@bp.post("/tick")
@csrf.exempt
def tick() -> ResponseReturnValue:
    """Cron-hosted heartbeat: same claim-scan as the thread, run synchronously.

    Exempt from CSRF because auth is the X-Tick-Token header (cron-job.org has
    no session cookies); any missing/short/wrong/unset token collapses to 404.
    """
    expected = current_app.config.get("TICK_TOKEN", "")
    given = request.headers.get("X-Tick-Token", "")
    if not expected or not hmac.compare_digest(expected, given):
        abort(404)
    return {"fired": scan_and_fire()}
