"""Events routes: reminders CRUD plus the spec's search-a-date day agenda."""

from __future__ import annotations

from flask import (
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy import select

from ...extensions import db
from ...models import Event
from ...services.agenda import day_events, parse_iso_day
from ...utils import get_own_or_404, ist_format, ist_to_utc_naive, log_action, utc_to_ist_wall
from . import bp
from .forms import EventForm


def _own_scheduled_or_404(event_id: int) -> Event:
    event = get_own_or_404(Event, event_id)
    if event.status != "scheduled":
        abort(404)
    return event


def _form_values(form: EventForm) -> dict:
    return {
        "title": form.title.data.strip(),
        "description": form.description.data,
        "event_at": ist_to_utc_naive(form.event_at.data),
        "repeat_rule": form.repeat_rule.data or "none",
        "alert_lead_minutes": (
            form.alert_lead_minutes.data if form.alert_lead_minutes.data is not None else 30
        ),
    }


@bp.get("")
def index() -> str:
    user_id = current_user.id
    upcoming = db.session.scalars(
        select(Event)
        .where(Event.user_id == user_id, Event.status == "scheduled")
        .order_by(Event.event_at)
        .limit(50)
    ).all()
    past = db.session.scalars(
        select(Event)
        .where(Event.user_id == user_id, Event.status != "scheduled")
        .order_by(Event.event_at.desc())
        .limit(20)
    ).all()
    return render_template("events/index.html", upcoming=upcoming, past=past)


@bp.route("/create", methods=["GET", "POST"])
def create() -> ResponseReturnValue:
    form = EventForm()
    if form.validate_on_submit():
        db.session.add(Event(user_id=current_user.id, **_form_values(form)))
        log_action(
            current_user.id,
            "event_created",
            form.title.data.strip()[:120],
            details=f"at {ist_format(ist_to_utc_naive(form.event_at.data))}",
        )
        db.session.commit()
        flash("Reminder created.")
        return redirect(url_for("events.index"))
    return render_template("events/form.html", form=form)


@bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
def edit(event_id: int) -> ResponseReturnValue:
    event = _own_scheduled_or_404(event_id)
    form = EventForm()
    if form.validate_on_submit():
        for key, value in _form_values(form).items():
            setattr(event, key, value)
        log_action(current_user.id, "event_updated", event.title[:120], event_id=event.id)
        db.session.commit()
        flash("Reminder updated.")
        return redirect(url_for("events.index"))
    form.title.data = event.title
    form.description.data = event.description
    form.event_at.data = utc_to_ist_wall(event.event_at)
    form.repeat_rule.data = event.repeat_rule
    form.alert_lead_minutes.data = event.alert_lead_minutes
    return render_template("events/form.html", form=form, event=event)


@bp.post("/<int:event_id>/cancel")
def cancel(event_id: int) -> Response:
    event = _own_scheduled_or_404(event_id)
    event.status = "cancelled"
    log_action(current_user.id, "event_cancelled", event.title[:120], event_id=event.id)
    db.session.commit()
    flash("Reminder cancelled.")
    return redirect(url_for("events.index"))


@bp.post("/<int:event_id>/delete")
def delete(event_id: int) -> Response:
    event = get_own_or_404(Event, event_id)
    log_action(current_user.id, "event_deleted", event.title[:120], details=event.status)
    db.session.delete(event)
    db.session.commit()
    flash("Reminder deleted.")
    return redirect(url_for("events.index"))


@bp.get("/day")
def day() -> str | tuple[str, int]:
    parsed = parse_iso_day(request.args.get("date", ""))
    if parsed is None:
        abort(404)
    rows = day_events(current_user.id, parsed)
    return render_template("events/day.html", day=parsed, events=rows)
