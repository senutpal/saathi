import sqlite3
from datetime import UTC, datetime

from click import echo
from flask import Flask, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event, select
from sqlalchemy.engine import Engine

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

PRAGMAS = (
    "PRAGMA foreign_keys=ON",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """WAL persists in the file; foreign_keys/synchronous/busy_timeout are per-connection."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        for pragma in PRAGMAS:
            cur.execute(pragma)
        cur.close()


def init_extensions(app: Flask) -> None:
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"
    # "strong" drops the session when the client fingerprint changes mid-session.
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def _load_user(user_id: str):
        # deferred: models import db from this module (circular-import wall)
        from .models import User

        # A plain SELECT, NOT db.session.get(): the scoped session keeps
        # expire_on_commit=False, so get() may serve a stale identity-map row
        # and miss a just-committed session_invalid_before bump (revocation
        # would silently lag). Re-reading per request makes the kill switch
        # take effect on the very next hit.
        user = db.session.scalar(select(User).where(User.id == int(user_id)))
        if user is None:
            return None
        # Global kill switch ("log out everywhere"): every cookie carries a
        # login_ts stamp (set by auth.finish_login); any cookie predating the
        # user's session_invalid_before — or lacking the stamp entirely, e.g.
        # pre-P13 cookies — resolves to an anonymous request. Runs here because
        # the loader executes on every authenticated request.
        ts = session.get("login_ts")
        invalid_before = user.session_invalid_before or datetime.min
        if ts is None or datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None) < invalid_before:
            return None
        return user

    csrf.init_app(app)
    limiter.init_app(app)


def init_db(app: Flask) -> None:
    from . import models  # noqa: F401  (must be imported before create_all)

    db.init_app(app)

    @app.cli.command("init-db")
    def _init_db_command() -> None:
        """Create all tables (idempotent)."""
        db.create_all()
        echo(f"database ready at {app.config['DATABASE_PATH']}")
