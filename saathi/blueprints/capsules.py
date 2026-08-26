"""Time capsule: letters to future you, revealed by the daily chore pass."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.validators import DataRequired, Length, ValidationError

from ..extensions import db
from ..models import CapsuleMessage
from ..models.base import utcnow
from ..utils import get_own_or_404, ist_to_utc_naive, log_action

bp = Blueprint("capsules", __name__, url_prefix="/capsules")

MIN_HORIZON = timedelta(hours=1)


class CapsuleForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=120)])
    body = TextAreaField("Letter", validators=[DataRequired(), Length(max=20000)])
    open_at = DateTimeLocalField("Opens on", validators=[DataRequired()])
    submit = SubmitField("Seal it")

    def __init__(self, now_fn: Callable[[], datetime] = utcnow, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._now_fn = now_fn

    def validate_open_at(self, field: DateTimeLocalField) -> None:
        if field.data is not None and ist_to_utc_naive(field.data) <= self._now_fn() + MIN_HORIZON:
            raise ValidationError("Capsules must stay sealed for at least an hour.")


@bp.get("")
@login_required
def index() -> str:
    rows = db.session.scalars(
        select(CapsuleMessage)
        .where(CapsuleMessage.user_id == current_user.id)
        .order_by(CapsuleMessage.open_at.desc())
    ).all()
    now = utcnow()
    cards = [(c, max(0, (c.open_at - now).days)) for c in rows]
    return render_template("capsules/index.html", capsules=cards)


@bp.route("/new", methods=["GET", "POST"])
def create() -> ResponseReturnValue:
    form = CapsuleForm()
    if form.validate_on_submit():
        capsule = CapsuleMessage(
            user_id=current_user.id,
            title=form.title.data.strip(),
            body=form.body.data,
            open_at=ist_to_utc_naive(form.open_at.data),
        )
        db.session.add(capsule)
        log_action(
            current_user.id,
            "capsule_sealed",
            form.title.data.strip(),
            details=f"opens {form.open_at.data:%Y-%m-%d}",
        )
        db.session.commit()
        flash("Sealed. Your future self will thank you.")
        return redirect(url_for(".index"))
    return render_template("capsules/new.html", form=form)


@bp.get("/<int:capsule_id>")
@login_required
def show(capsule_id: int) -> str | tuple[str, int]:
    capsule = get_own_or_404(CapsuleMessage, capsule_id)
    revealed = capsule.status == "opened" and capsule.open_at <= utcnow()
    return render_template("capsules/show.html", capsule=capsule, revealed=revealed)
