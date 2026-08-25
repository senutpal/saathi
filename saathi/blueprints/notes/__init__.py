"""Notes blueprint: markdown notes with tags, search and soft-delete trash."""

from flask import Blueprint, redirect, request, url_for
from flask_login import current_user

bp = Blueprint("notes", __name__, url_prefix="/notes")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


from . import (  # noqa: E402,F401  (routes imports bp from this module; bottom-import breaks the cycle)
    routes,
)
