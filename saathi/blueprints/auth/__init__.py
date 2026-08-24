"""Auth blueprint: register, login, logout."""

from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/auth")

from . import (  # noqa: E402,F401  (routes imports bp from this module; bottom-import breaks the cycle)
    routes,
)
