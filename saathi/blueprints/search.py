"""Web-search blueprint: throttled keyless metasearch over the cached service."""

from __future__ import annotations

import time

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user

from ..services.search import lookup_cached, search_web

bp = Blueprint("search", __name__, url_prefix="/search")

SEARCH_MIN_INTERVAL_SECONDS = 3.0
MAX_QUERY_LENGTH = 200


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@bp.get("")
def search() -> str:
    """Empty/over-long queries re-render the form before any network touch;
    cache hits render free of the throttle, which arms on network searches only."""
    q = (request.args.get("q") or "").strip()
    outcome = lookup_cached(q) if q else None
    hint: str | None = None
    if len(q) > MAX_QUERY_LENGTH:
        hint = f"Keep queries under {MAX_QUERY_LENGTH} characters."
        outcome = None
    elif q and outcome is None:
        waited = time.time() - session.get("last_search_ts", 0.0)
        if waited < SEARCH_MIN_INTERVAL_SECONDS:
            flash("One search every few seconds, please.", "warn")
        else:
            outcome = search_web(q, current_user.id)
            if outcome["source"] != "cached":
                session["last_search_ts"] = time.time()
    return render_template("search/results.html", q=q, outcome=outcome, hint=hint)
