"""Habits blueprint: daily toggles feeding streaks and the dashboard card."""

from __future__ import annotations

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
from wtforms import SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional

from ..extensions import db
from ..models import Habit, HabitLog
from ..utils import get_own_or_404, ist_today, log_action

bp = Blueprint("habits", __name__, url_prefix="/habits")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


# Palette KEYS only — templates resolve them to literal class strings (B17 P6).
PALETTE: tuple[str, ...] = ("sky", "emerald", "amber", "rose", "violet")


class HabitForm(FlaskForm):
    name = StringField("Habit", validators=[DataRequired(), Length(max=80)])
    color = SelectField(
        "Color",
        choices=[(key, key.capitalize()) for key in PALETTE],
        default="emerald",
        validators=[Optional()],
    )


def _own_habits() -> list[Habit]:
    return list(
        db.session.scalars(select(Habit).where(Habit.user_id == current_user.id).order_by(Habit.id))
    )


@bp.get("")
def index() -> str:
    form = HabitForm()
    habits = _own_habits()
    done_today = set()
    if habits:
        today = ist_today()
        done_today = set(
            db.session.scalars(
                select(HabitLog.habit_id).where(
                    HabitLog.habit_id.in_([h.id for h in habits]), HabitLog.log_date == today
                )
            )
        )
    return render_template(
        "habits/index.html",
        rows=_overview(habits, done_today),
        form=form,
        palette=PALETTE,
    )


@bp.post("/add")
def add() -> ResponseReturnValue:
    form = HabitForm()
    if form.validate_on_submit():
        db.session.add(
            Habit(user_id=current_user.id, name=form.name.data.strip(), color=form.color.data)
        )
        log_action(current_user.id, "habit_created", f"Started habit {form.name.data.strip()[:80]}")
        db.session.commit()
        flash("Habit added.")
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(message, "error")
    return redirect(url_for("habits.index"))


@bp.post("/<int:habit_id>/toggle")
def toggle(habit_id: int) -> ResponseReturnValue:
    habit = get_own_or_404(Habit, habit_id)
    day = ist_today()
    logged = db.session.scalar(
        select(HabitLog).where(HabitLog.habit_id == habit.id, HabitLog.log_date == day)
    )
    if logged is not None:
        db.session.delete(logged)
        action = "Undone"
    else:
        # The UNIQUE pair constraint backstops any double-submit race.
        db.session.add(HabitLog(habit_id=habit.id, log_date=day))
        action = "Done"
    log_action(current_user.id, "habit_toggled", f"{action}: {habit.name[:100]}")
    db.session.commit()
    return redirect(url_for("habits.index"))


@bp.post("/<int:habit_id>/delete")
def delete(habit_id: int) -> ResponseReturnValue:
    habit = get_own_or_404(Habit, habit_id)
    log_action(current_user.id, "habit_deleted", f"Removed habit {habit.name[:80]}")
    db.session.delete(habit)
    db.session.commit()
    flash("Habit deleted.")
    return redirect(url_for("habits.index"))


def _overview(habits: list[Habit], done_today: set[int]) -> list[dict]:
    """Template-facing rows; streak/grid fields arrive with S4."""
    return [
        {"habit": h, "done_today": h.id in done_today, "current": 0, "longest": 0, "days": []}
        for h in habits
    ]
