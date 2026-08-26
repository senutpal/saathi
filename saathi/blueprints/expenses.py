"""Expenses blueprint: integer-cents ledger with monthly category bars."""

from __future__ import annotations

from datetime import timedelta
from decimal import InvalidOperation

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
from sqlalchemy import func, select
from wtforms import DateField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ..extensions import db
from ..models import Expense
from ..services.money import parse_to_cents
from ..utils import get_own_or_404, ist_today, log_action, month_bounds

bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


CATEGORIES = ("food", "travel", "books", "bills", "fun", "other")


class ExpenseForm(FlaskForm):
    amount = StringField("Amount", validators=[DataRequired(), Length(max=12)])
    category = StringField("Category", validators=[DataRequired(), Length(max=40)])
    spent_on = DateField("Date", format="%Y-%m-%d", validators=[DataRequired()])
    note = TextAreaField("Note", validators=[Optional(), Length(max=500)])

    def validate_amount(self, field: object) -> None:
        try:
            self.cents: int = parse_to_cents(field.data)
        except (ValueError, InvalidOperation) as exc:
            raise ValidationError("Enter an amount like 250 or 49.99 (max 2 decimals).") from exc


@bp.get("")
def index() -> str:
    first, after = month_bounds(request.args.get("month"))
    entries = list(
        db.session.scalars(
            select(Expense)
            .where(
                Expense.user_id == current_user.id,
                Expense.spent_on >= first,
                Expense.spent_on < after,
            )
            .order_by(Expense.spent_on.desc(), Expense.id.desc())
        )
    )
    by_category = dict(
        db.session.execute(
            select(Expense.category, func.sum(Expense.amount_cents))
            .where(
                Expense.user_id == current_user.id,
                Expense.spent_on >= first,
                Expense.spent_on < after,
            )
            .group_by(Expense.category)
        ).all()
    )
    total_cents = sum(by_category.values(), 0)
    prev_link = (first - timedelta(days=1)).replace(day=1).isoformat()[:7]
    return render_template(
        "expenses/index.html",
        form=ExpenseForm(),
        entries=entries,
        by_category=dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        total_cents=total_cents,
        month_label=f"{first:%B %Y}",
        month_param=first.isoformat()[:7],
        prev_param=prev_link,
        next_param=after.isoformat()[:7],
        categories=CATEGORIES,
        now_iso=ist_today().isoformat(),
    )


@bp.post("/add")
def add() -> ResponseReturnValue:
    form = ExpenseForm()
    if form.validate_on_submit():
        db.session.add(
            Expense(
                user_id=current_user.id,
                amount_cents=form.cents,
                spent_on=form.spent_on.data or ist_today(),
                category=form.category.data.strip().lower(),
                note=form.note.data,
            )
        )
        log_action(
            current_user.id,
            "expense_added",
            f"Spent {form.amount.data.strip()} on {form.category.data.strip()[:30]}",
        )
        db.session.commit()
        flash("Expense added.")
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(message, "error")
    return redirect(url_for("expenses.index"))


@bp.post("/<int:expense_id>/delete")
def delete(expense_id: int) -> ResponseReturnValue:
    expense = get_own_or_404(Expense, expense_id)
    log_action(current_user.id, "expense_deleted", f"Removed {expense.category} entry")
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.")
    return redirect(url_for("expenses.index"))
