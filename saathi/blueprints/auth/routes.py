"""Register / login / logout handlers."""

from __future__ import annotations

import time

from flask import Response, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ...extensions import db, limiter
from ...models import LoginRecord, User
from ...models.base import utcnow
from ...services import lockout, twofa
from ...utils import log_action, safe_next
from . import bp
from .forms import LoginForm, RegisterForm, TwoFaLoginForm

DUMMY_HASH = generate_password_hash("not-a-real-password-at-all")
LOGIN_FAILED_MESSAGE = "Invalid email or password"
PRE_2FA_TTL = 300  # seconds a half-session may wait for its code


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
            if user.twofa_enabled:
                # Password alone is not a login: park the half-session and
                # demand the second factor (B16 §1.3).
                session.clear()
                session["pre_2fa_user_id"] = user.id
                session["pre_2fa_at"] = time.time()
                return redirect(url_for("auth.two_fa"))
            lockout.clear_failures(email)
            return finish_login(user)
        flash(LOGIN_FAILED_MESSAGE, "error")
        lockout.record_failure(email)
        # Re-render clean: keeps wrong-password and unknown-email responses
        # byte-identical (no echoed email — flash carries the failure).
        # formdata={} defeats FlaskForm's auto-bind of request.form.
        form = LoginForm(formdata={})
    return render_template("auth/login.html", form=form, next_target=next_target)


@bp.route("/login/two-fa", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def two_fa() -> str | Response:
    """Second factor after a good password; no pre_2fa stash -> login page."""
    uid = session.get("pre_2fa_user_id")
    if not uid or time.time() - session.get("pre_2fa_at", 0) > PRE_2FA_TTL:
        session.pop("pre_2fa_user_id", None)
        return redirect(url_for("auth.login"))
    user = db.session.scalar(db.select(User).where(User.id == uid))
    if user is None:
        session.pop("pre_2fa_user_id", None)
        return redirect(url_for("auth.login"))
    # the brute-force door stays shut here too: a locked account never sees
    # the code form again (same uniform message as the login page)
    if lockout.is_locked(user.email):
        flash(LOGIN_FAILED_MESSAGE, "error")
        return redirect(url_for("auth.login"))
    form = TwoFaLoginForm()
    if form.validate_on_submit():
        raw = form.code.data.strip().upper()
        if twofa.verify_login_code(user, raw):
            lockout.clear_failures(user.email)
            # finish_login's session.clear() also drops the pre_2fa keys
            return finish_login(user)
        # a 6-digit keyspace is brute-forceable without ledger accounting
        lockout.record_failure(user.email)
        # identical wording whether TOTP or backup failed — never reveal
        # which factor mismatched
        flash("That code didn't match.", "error")
    return render_template("auth/two_fa.html", form=form)


@bp.post("/logout")
@login_required
def logout() -> Response:
    log_action(current_user.id, "logout", "Signed out")
    db.session.commit()
    logout_user()
    session.clear()
    return redirect(url_for("main.index"))
