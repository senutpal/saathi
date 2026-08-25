"""Notifications blueprint: bell badge poll, inbox and mark-read flows."""

from __future__ import annotations

import math

from flask import (
    Blueprint,
    Response,
    abort,
    has_request_context,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select, update

from ..extensions import db
from ..models import Notification
from ..models.base import utcnow
from ..utils import log_action

bp = Blueprint("notifications", __name__, url_prefix="/notifications")

PAGE_SIZE = 25
PREVIEW_LIMIT = 5


def _unread_filter():
    return (Notification.user_id == current_user.id, Notification.read_at.is_(None))


def bell_context() -> dict:
    """Server-side first paint for the topbar bell (count + newest preview).

    Skipped on the poll endpoint itself so every bell ping stays at
    auth-load + one covering-index COUNT; also skipped outside request
    contexts (email thread renders trigger context processors too).
    """
    if (
        not has_request_context()
        or not current_user.is_authenticated
        or request.endpoint == "notifications.count"
    ):
        return {}
    unread = db.session.scalar(
        select(func.count()).select_from(Notification).where(*_unread_filter())
    )
    items = list(
        db.session.scalars(
            select(Notification)
            .where(*_unread_filter())
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(PREVIEW_LIMIT)
        )
    )
    return {"bell_unread": unread, "bell_items": items}


@bp.get("/count")
def count():
    # Manual auth check instead of @login_required: an expired session must NOT
    # redirect the poll to the login page (htmx would swap it into the bell);
    # 286 tells htmx to cancel polling cleanly.
    if not current_user.is_authenticated:
        return Response(status=286)
    unread = db.session.scalar(
        select(func.count()).select_from(Notification).where(*_unread_filter())
    )
    return render_template("partials/_bell_count.html", bell_unread=unread)


@bp.get("")
@login_required
def inbox():
    total = db.session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id)
    )
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    items = list(
        db.session.scalars(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    )
    return render_template(
        "notifications/inbox.html", items=items, page=page, pages=pages, total=total
    )


@bp.post("/<int:nid>/read")
@login_required
def mark_read(nid: int):
    notification = db.session.scalar(
        select(Notification).where(Notification.id == nid, Notification.user_id == current_user.id)
    )
    if notification is None:
        abort(404)
    notification.read_at = utcnow()
    db.session.commit()
    return redirect(url_for(".inbox"))


@bp.post("/read-all")
@login_required
def read_all():
    result = db.session.execute(
        update(Notification).where(*_unread_filter()).values(read_at=utcnow())
    )
    if result.rowcount:
        log_action(
            current_user.id,
            "notifications_read_all",
            f"Marked {result.rowcount} notifications read",
        )
    db.session.commit()
    return redirect(url_for(".inbox"))
