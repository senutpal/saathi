"""Settings routes: ICS feed, digest, and the Security page (2FA/sessions)."""

from __future__ import annotations

import segno
from flask import Blueprint, Response, flash, redirect, render_template, session, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required, logout_user
from sqlalchemy import delete, select

from ..extensions import db
from ..models import BackupCode, LoginRecord
from ..models.base import utcnow
from ..services import twofa
from ..services.daily import digest_context
from ..services.ics import new_token
from ..utils import external_url, log_action
from .auth.forms import TwoFaConfirmForm, TwoFaDisableForm

bp = Blueprint("settings", __name__)

SETUP_TRY_LIMIT = 5


@bp.get("/settings")
@login_required
def index() -> str:
    # lazy mint: the token exists only once the owner first opens this page
    if not current_user.ics_token:
        current_user.ics_token = new_token()
        db.session.commit()
    return render_template(
        "settings/index.html",
        ics_url=external_url("calendar.ics", token=current_user.ics_token),
    )


@bp.post("/settings/calendar-token/regenerate")
@login_required
def regenerate() -> ResponseReturnValue:
    current_user.ics_token = new_token()
    log_action(current_user.id, "settings_updated", "Calendar feed link regenerated")
    db.session.commit()
    flash("New calendar link generated; the old link no longer works.")
    return redirect(url_for("settings.index"))


@bp.post("/settings/digest-toggle")
@login_required
def digest_toggle() -> ResponseReturnValue:
    current_user.digest_enabled = not current_user.digest_enabled
    detail = "Weekly digest enabled" if current_user.digest_enabled else "Weekly digest disabled"
    log_action(current_user.id, "settings_updated", detail)
    db.session.commit()
    flash(detail + ".")
    return redirect(url_for("settings.index"))


@bp.get("/digest/preview")
@login_required
def digest_preview() -> Response:
    """The exact email document, standalone — report-screenshot friendly."""
    ctx = digest_context(current_user, now_fn=utcnow)
    return Response(render_template("emails/digest.html", **ctx), mimetype="text/html")


# --- Security page: 2FA, backup codes, sign-ins ---------------------------


def _recent_logins() -> list[LoginRecord]:
    return list(
        db.session.scalars(
            select(LoginRecord)
            .where(LoginRecord.user_id == current_user.id)
            .order_by(LoginRecord.at.desc(), LoginRecord.id.desc())
            .limit(10)
        )
    )


def _render_security(**extra: object) -> str:
    ctx: dict[str, object] = {
        "disable_form": TwoFaDisableForm(),
        "recent_logins": _recent_logins(),
        "unused_codes": twofa.unused_backup_count(current_user),
    }
    ctx.update(extra)
    return render_template("settings/security.html", **ctx)


@bp.get("/settings/security")
@login_required
def security() -> str:
    return _render_security()


@bp.post("/settings/two-fa/enable")
@login_required
def two_fa_enable() -> ResponseReturnValue:
    if current_user.twofa_enabled:
        return redirect(url_for("settings.security"))
    # store BEFORE confirm (crash-safe): a half-done setup leaves an inert,
    # unverified secret; twofa_enabled only flips once a code proves it
    current_user.totp_secret = twofa.new_secret()
    session.pop("twofa_setup_tries", None)
    db.session.commit()
    uri = twofa.provisioning_uri(current_user)
    qr_uri = segno.make(uri, error="m").svg_data_uri(scale=4, border=2)
    return render_template(
        "settings/two_fa_setup.html",
        qr_uri=qr_uri,
        manual_secret=twofa.grouped_secret(current_user.totp_secret or ""),
        form=TwoFaConfirmForm(),
    )


def _render_setup(form: TwoFaConfirmForm) -> str:
    uri = twofa.provisioning_uri(current_user)
    qr_uri = segno.make(uri, error="m").svg_data_uri(scale=4, border=2)
    return render_template(
        "settings/two_fa_setup.html",
        qr_uri=qr_uri,
        manual_secret=twofa.grouped_secret(current_user.totp_secret or ""),
        form=form,
    )


@bp.post("/settings/two-fa/confirm")
@login_required
def two_fa_confirm() -> ResponseReturnValue:
    if current_user.twofa_enabled or not current_user.totp_secret:
        return redirect(url_for("settings.security"))
    form = TwoFaConfirmForm()
    code = (form.code.data or "").strip().replace(" ", "")
    ok = bool(code) and twofa.verify_existing_code(current_user, code)
    if not ok:
        tries = int(session.get("twofa_setup_tries", 0)) + 1
        session["twofa_setup_tries"] = tries
        if tries >= SETUP_TRY_LIMIT:
            # too many bad codes: burn the unverified secret, restart cleanly
            current_user.totp_secret = None
            db.session.commit()
            session.pop("twofa_setup_tries", None)
            flash("Too many attempts — two-factor setup has restarted.", "error")
            return redirect(url_for("settings.security"))
        flash("That code didn't match — try again.", "error")
        return _render_setup(form)
    current_user.twofa_enabled = True
    codes = twofa.generate_backup_codes()
    twofa.store_backup_codes(current_user, codes)
    log_action(current_user.id, "settings_updated", "Two-factor authentication enabled")
    db.session.commit()
    flash("2FA is on — save your backup codes now.")
    return render_template("settings/backup_codes.html", codes=codes)


@bp.post("/settings/two-fa/backup-codes/regenerate")
@login_required
def backup_codes_regenerate() -> ResponseReturnValue:
    if not current_user.twofa_enabled:
        return redirect(url_for("settings.security"))
    codes = twofa.generate_backup_codes()
    twofa.store_backup_codes(current_user, codes)
    log_action(current_user.id, "settings_updated", "Backup codes regenerated")
    db.session.commit()
    flash("New backup codes generated; every old code is now void.")
    return render_template("settings/backup_codes.html", codes=codes)


@bp.post("/settings/two-fa/disable")
@login_required
def two_fa_disable() -> ResponseReturnValue:
    form = TwoFaDisableForm()
    if not form.validate_on_submit():
        return _render_security(disable_form=form)
    if not current_user.check_password(form.password.data):
        flash("Password didn't match — 2FA stays on.", "error")
        return redirect(url_for("settings.security"))
    if not twofa.verify_existing_code(current_user, (form.code.data or "").strip()):
        flash("That code didn't match — 2FA stays on.", "error")
        return redirect(url_for("settings.security"))
    current_user.twofa_enabled = False
    current_user.totp_secret = None
    db.session.execute(delete(BackupCode).where(BackupCode.user_id == current_user.id))
    log_action(current_user.id, "settings_updated", "Two-factor authentication disabled")
    db.session.commit()
    flash("Two-factor authentication is off.")
    return redirect(url_for("settings.security"))


@bp.post("/settings/logout-everywhere")
@login_required
def logout_everywhere() -> ResponseReturnValue:
    """Bump the global cookie kill stamp, then end this very session."""
    current_user.session_invalid_before = utcnow()
    log_action(current_user.id, "settings_updated", "Logged out all devices")
    db.session.commit()
    logout_user()
    session.clear()
    flash("Every signed-in device has been logged out. Sign in again to continue.")
    return redirect(url_for("auth.login"))
