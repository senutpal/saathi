"""Register / login / logout handlers."""

from __future__ import annotations

import time

from flask import Response, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db, limiter
from ...models import LoginRecord, User
from ...models.base import utcnow
from ...utils import log_action, safe_next
from . import bp, lockout
from .forms import LoginForm, RegisterForm

DUMMY_HASH = generate_password_hash("not-a-real-password-at-all")
LOGIN_FAILED_MESSAGE = "Invalid email or password"


def finish_login(user: User) -> Response:
    """Complete a fully authenticated login (password-only or 2FA path).

    Single choke point for: session regeneration (clear before login_user),
    the cookie's login_ts stamp (user_loader revocation compares against it),
    the LoginRecord audit row, and the validated ?next= redirect.
    """
    # Flask sessions are signed cookies with nothing server-side to rotate,
    # so fixation defense is this explicit clear (B03 §5 pitfall).
    session.clear()
    login_user(user)
    session["login_ts"] = time.time()
    db.session.add(
        LoginRecord(
            user_id=user.id,
            at=utcnow(),
            ip=(request.remote_addr or "")[:45] or None,
            user_agent=(str(request.user_agent) or "")[:200] or None,
        )
    )
    log_action(user.id, "login", "Signed in")
    db.session.commit()
    flash(f"Welcome back, {user.username}.")
    next_target = request.values.get("next")
    return redirect(safe_next(next_target) or url_for("main.index"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register() -> str | Response:
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.strip(), email=form.email.data.lower())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        log_action(user.id, "signup", "Joined Saathi")
        db.session.commit()
        flash("Account created — sign in to continue.")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login() -> str | Response:
    next_target = request.values.get("next")
    if current_user.is_authenticated:
        return redirect(safe_next(next_target) or url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        # Lockout gate BEFORE any password work: burn the same scrypt path and
        # render the byte-identical failure body, so a locked account is
        # indistinguishable from a wrong password (no "account locked" leak).
        if lockout.is_locked(email):
            check_password_hash(DUMMY_HASH, form.password.data)
            flash(LOGIN_FAILED_MESSAGE, "error")
            form = LoginForm(formdata={})
            return render_template("auth/login.html", form=form, next_target=next_target)
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is not None:
            ok = user.check_password(form.password.data)
        else:
            # Burn the same scrypt CPU path for unknown emails so response timing
            # cannot reveal which addresses are registered (anti-enumeration).
            check_password_hash(DUMMY_HASH, form.password.data)
            ok = False
        if ok and user is not None:
            lockout.clear_failures(email)
            return finish_login(user)
        flash(LOGIN_FAILED_MESSAGE, "error")
        lockout.record_failure(email)
        # Re-render clean: keeps wrong-password and unknown-email responses
        # byte-identical (no echoed email — flash carries the failure).
        # formdata={} defeats FlaskForm's auto-bind of request.form.
        form = LoginForm(formdata={})
    return render_template("auth/login.html", form=form, next_target=next_target)


@bp.post("/logout")
@login_required
def logout() -> Response:
    log_action(current_user.id, "logout", "Signed out")
    db.session.commit()
    logout_user()
    session.clear()
    return redirect(url_for("main.index"))
