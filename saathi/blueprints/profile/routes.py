"""Profile routes: personal-data view/edit plus education/work entry CRUD."""

from __future__ import annotations

from flask import Response, flash, redirect, render_template, url_for
from flask_login import current_user

from ...extensions import db
from ...models import Profile
from . import bp
from .forms import ProfileForm


def _current_profile() -> Profile:
    prof = current_user.profile
    if prof is None:
        prof = Profile(user_id=current_user.id)
        db.session.add(prof)
    return prof


@bp.get("")
def view() -> str:
    return render_template("profile/view.html", profile=current_user.profile)


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
