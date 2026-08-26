"""Contacts blueprint: address-book rows feeding the birthday engine."""

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
from wtforms import DateField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

from ..extensions import db
from ..models import Contact
from ..utils import PHONE_CHARS, get_own_or_404, log_action

bp = Blueprint("contacts", __name__, url_prefix="/contacts")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Length(max=30)])
    email = StringField("Email", validators=[Optional(), Length(max=255), Email()])
    dob = DateField("Birthday", format="%Y-%m-%d", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Length(max=2000)])

    def validate_phone(self, field: object) -> None:
        # Charset allowlist only: rejects letters, never a valid format.
        if field.data and not all(PHONE_CHARS.fullmatch(ch) for ch in field.data):
            raise ValidationError("Phone may contain digits, spaces and + - ( ) . only.")


@bp.get("")
def index() -> str:
    contacts = db.session.scalars(
        select(Contact)
        .where(Contact.user_id == current_user.id)
        .order_by(Contact.name.asc(), Contact.id.asc())
    ).all()
    return render_template("contacts/index.html", contacts=contacts, form=ContactForm())


@bp.post("/add")
def add() -> ResponseReturnValue:
    form = ContactForm()
    if form.validate_on_submit():
        db.session.add(
            Contact(
                user_id=current_user.id,
                name=form.name.data.strip(),
                phone=form.phone.data,
                email=form.email.data,
                dob=form.dob.data,
                notes=form.notes.data,
            )
        )
        log_action(current_user.id, "contact_saved", f"Added contact {form.name.data.strip()[:80]}")
        db.session.commit()
        flash("Contact added.")
        return redirect(url_for("contacts.index"))
    _flash_errors(form)
    return redirect(url_for("contacts.index"))


@bp.route("/<int:contact_id>/edit", methods=["GET", "POST"])
def edit(contact_id: int) -> ResponseReturnValue:
    contact = get_own_or_404(Contact, contact_id)
    form = ContactForm(obj=contact)
    if form.validate_on_submit():
        form.populate_obj(contact)
        contact.name = contact.name.strip()
        log_action(current_user.id, "contact_saved", f"Updated contact {contact.name[:80]}")
        db.session.commit()
        flash("Contact updated.")
        return redirect(url_for("contacts.index"))
    return render_template("contacts/edit.html", form=form, contact=contact)


@bp.post("/<int:contact_id>/delete")
def delete(contact_id: int) -> ResponseReturnValue:
    contact = get_own_or_404(Contact, contact_id)
    log_action(current_user.id, "contact_deleted", f"Removed contact {contact.name[:80]}")
    db.session.delete(contact)
    db.session.commit()
    flash("Contact deleted.")
    return redirect(url_for("contacts.index"))


def _flash_errors(form: FlaskForm) -> None:
    for messages in form.errors.values():
        for message in messages:
            flash(message, "error")
