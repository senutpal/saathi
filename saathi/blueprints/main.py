import hmac
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from ..extensions import csrf, db
from ..models import Event, Note
from ..models.base import utcnow
from ..services.briefing import build_briefing
from ..services.quickadd import parse_quick_add
from ..services.scheduler import scan_and_fire
from ..utils import get_own_or_404, ist_format, log_action

bp = Blueprint("main", __name__)

UNDO_GRACE = timedelta(minutes=5)


@bp.get("/")
@login_required
def index() -> str:
    return render_template(
        "main/home.html", undo_event=undo_context(), **build_briefing(current_user.id)
    )


@bp.post("/quick-add")
@login_required
def quick_add() -> ResponseReturnValue:
    text = request.form.get("text", "").strip()
    if not text:
        flash("Type something like: rem tomorrow 6pm pay fees", "error")
        return redirect(url_for("main.index"))
    kind, when, title = parse_quick_add(text)
    if kind == "event":
        event = Event(user_id=current_user.id, title=title, event_at=when)
        db.session.add(event)
        log_action(
            current_user.id,
            "event_created",
            title,
            details=f"quick-add for {ist_format(when)}",
        )
        db.session.flush()
        session["pending_undo"] = {
            "id": event.id,
            "title": event.title,
            "when": when.isoformat(),
            "ts": utcnow().isoformat(),
        }
        db.session.commit()
        flash(f"Reminder created for {ist_format(when)}.")
    else:
        db.session.add(Note(user_id=current_user.id, title=title, content=""))
        log_action(current_user.id, "note_created", title, details="quick-add")
        db.session.commit()
        flash("Note created from quick-add.")
    return redirect(url_for("main.index"))


@bp.post("/quick-add/<int:event_id>/undo")
@login_required
def quick_add_undo(event_id: int) -> ResponseReturnValue:
    pending = session.pop("pending_undo", None)
    if not pending or pending["id"] != event_id:
        abort(404)
    event = get_own_or_404(Event, event_id)
    age = utcnow() - datetime.fromisoformat(str(pending["ts"]))
    unchanged = event.title == pending["title"] and event.event_at.isoformat() == pending["when"]
    fresh = age <= UNDO_GRACE
    untouched = event.fired_at is None and event.status == "scheduled"
    if not (fresh and unchanged and untouched):
        abort(404)
    db.session.delete(event)
    log_action(current_user.id, "event_deleted", event.title[:120], details="quick-add undone")
    db.session.commit()
    flash("Reminder undone.")
    return redirect(url_for("main.index"))


def undo_context() -> dict | None:
    """The still-valid quick-add creation for the dashboard undo bar."""
    pending = session.get("pending_undo")
    if not pending:
        return None
    ts = datetime.fromisoformat(str(pending["ts"]))
    if utcnow() - ts > UNDO_GRACE:
        return None
    event = db.session.get(Event, int(pending["id"]))
    if event is None or event.user_id != current_user.id or event.status != "scheduled":
        return None
    return {"id": event.id, "title": event.title, "when": event.event_at}


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
