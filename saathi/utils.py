"""Shared request-level helpers: safe redirects, owned fetches, audit rows."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import abort
from flask_login import current_user

from .extensions import db
from .models import ActivityLog


def safe_next(target: str | None) -> str:
    """Return target only if it is a site-relative path ('/x'), else ''.

    Rejects protocol-relative '//host', backslash variants and absolute URLs,
    so a forged ?next= can never bounce a login off-site.
    """
    if not target or "\\" in target:
        return ""
    parts = urlsplit(target)
    is_relative = parts.scheme == "" and parts.netloc == ""
    starts_safe = target.startswith("/") and not target.startswith("//")
    if is_relative and starts_safe:
        return target
    return ""


def get_own_or_404(model: type[db.Model], obj_id: int) -> db.Model:
    """MANDATORY for any fetch of another-user-reachable resource.

    The owner filter rides inside the fetch, so a foreign id is
    indistinguishable from a missing one (404, never 403 — no existence leak).
    """
    obj = model.query.filter_by(id=obj_id, user_id=current_user.id).first()
    if obj is None:
        abort(404)
    return obj


def log_action(user_id: int, activity_type: str, title: str, details: str | None = None) -> None:
    """Queue an ActivityLog row (ADR-015 shape) on the current transaction; caller commits.

    Same-transaction rule (B08 pitfall #8): an audit row must live or die with
    the mutation it describes. Verbs come from the B08 VOCAB set.
    """
    db.session.add(
        ActivityLog(user_id=user_id, activity_type=activity_type, title=title, details=details)
    )
