"""Profile routes: personal-data view/edit plus education/work entry CRUD."""

from __future__ import annotations

from flask import Response, flash, redirect, render_template, url_for
from flask_login import current_user

from ...extensions import db
from ...models import EducationEntry, Profile, WorkEntry
from ...utils import get_own_or_404
from . import bp
from .forms import EducationForm, ProfileForm, WorkForm


def _current_profile() -> Profile:
    prof = current_user.profile
    if prof is None:
        prof = Profile(user_id=current_user.id)
        db.session.add(prof)
    return prof


def _flash_form_errors(form: EducationForm | WorkForm | ProfileForm) -> None:
    for messages in form.errors.values():
        for message in messages:
            flash(message, "error")


@bp.get("")
def view() -> str:
    return render_template(
        "profile/view.html",
        profile=current_user.profile,
        education_form=EducationForm(),
        work_form=WorkForm(),
    )


@bp.route("/edit", methods=["GET", "POST"])
def edit() -> str | Response:
    form = ProfileForm(obj=current_user.profile)
    if form.validate_on_submit():
        prof = _current_profile()
        form.populate_obj(prof)
        prof.full_name = prof.full_name.strip()
        db.session.commit()
        flash("Profile saved.")
        return redirect(url_for("profile.view"))
    return render_template("profile/edit.html", form=form)


@bp.post("/education/new")
def education_new() -> Response:
    form = EducationForm()
    if form.validate_on_submit():
        db.session.add(_education_entry(form))
        db.session.commit()
        flash("Education entry added.")
    else:
        _flash_form_errors(form)
    return redirect(url_for("profile.view"))


@bp.post("/education/<int:eid>/delete")
def education_delete(eid: int) -> Response:
    entry = get_own_or_404(EducationEntry, eid)
    db.session.delete(entry)
    db.session.commit()
    flash("Education entry deleted.")
    return redirect(url_for("profile.view"))


@bp.post("/work/new")
def work_new() -> Response:
    form = WorkForm()
    if form.validate_on_submit():
        db.session.add(_work_entry(form))
        db.session.commit()
        flash("Work entry added.")
    else:
        _flash_form_errors(form)
    return redirect(url_for("profile.view"))


@bp.post("/work/<int:wid>/delete")
def work_delete(wid: int) -> Response:
    entry = get_own_or_404(WorkEntry, wid)
    db.session.delete(entry)
    db.session.commit()
    flash("Work entry deleted.")
    return redirect(url_for("profile.view"))


def _education_entry(form: EducationForm) -> EducationEntry:
    return EducationEntry(
        user_id=current_user.id,
        institution=form.institution.data.strip(),
        qualification=form.qualification.data.strip(),
        field_of_study=form.field_of_study.data,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        description=form.description.data,
    )


def _work_entry(form: WorkForm) -> WorkEntry:
    return WorkEntry(
        user_id=current_user.id,
        organization=form.organization.data.strip(),
        role=form.role.data.strip(),
        location=form.location.data,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        description=form.description.data,
    )
