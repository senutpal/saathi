"""Mood journal blueprint: one score per IST day, month view."""

from __future__ import annotations

from datetime import timedelta

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import DateField, RadioField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ..extensions import db
from ..models import Mood
from ..utils import ist_today, log_action, month_bounds

bp = Blueprint("mood", __name__, url_prefix="/mood")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


class MoodForm(FlaskForm):
    mood_date = DateField("Date", format="%Y-%m-%d", validators=[DataRequired()])
    score = RadioField(
        "Mood",
        choices=[(1, "Rough"), (2, "Low"), (3, "Okay"), (4, "Good"), (5, "Great")],
        coerce=int,
        validators=[DataRequired()],
    )
    note = TextAreaField("Note", validators=[Optional(), Length(max=2000)])


@bp.get("")
def index() -> str:
    first, after = month_bounds(request.args.get("month"))
    form = MoodForm()
    form.mood_date.data = form.mood_date.data or ist_today()
    entries = list(
        db.session.scalars(
            select(Mood)
            .where(
                Mood.user_id == current_user.id,
                Mood.mood_date >= first,
                Mood.mood_date < after,
            )
            .order_by(Mood.mood_date)
        )
    )
    scores = [entry.score for entry in entries]
    average = round(sum(scores) / len(scores), 1) if scores else None
    prev_link = (first - timedelta(days=1)).replace(day=1).isoformat()[:7]
    next_month = after.replace(day=1)
    return render_template(
        "mood/index.html",
        form=form,
        entries=entries,
        scores=scores,
        average=average,
        month_label=f"{first:%B %Y}",
        month_param=first.isoformat()[:7],
        prev_param=prev_link,
        next_param=next_month.isoformat()[:7],
    )


@bp.post("/set")
def set_mood() -> ResponseReturnValue:
    form = MoodForm()
    if not form.validate_on_submit():
        for messages in form.errors.values():
            for message in messages:
                flash(message, "error")
        return redirect(url_for("mood.index"))
    day = form.mood_date.data
    # Read-then-write upsert (B17 P3): a second POST must UPDATE, never hit
    # uq_moods_user_date as a 500.
    existing = db.session.scalar(
        select(Mood).where(Mood.user_id == current_user.id, Mood.mood_date == day)
    )
    if existing is None:
        db.session.add(
            Mood(user_id=current_user.id, mood_date=day, score=form.score.data, note=form.note.data)
        )
        verb_detail = f"Mood {form.score.data}/5 logged"
    else:
        existing.score = form.score.data
        existing.note = form.note.data
        verb_detail = f"Mood {form.score.data}/5 updated"
    log_action(current_user.id, "mood_set", verb_detail)
    db.session.commit()
    flash("Mood saved.")
    return redirect(url_for("mood.index", month=day.isoformat()[:7]))
