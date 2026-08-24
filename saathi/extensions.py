import sqlite3

from click import echo
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
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

    @login_manager.user_loader
    def _placeholder_loader(user_id: str):
        return None  # real lookup lands in P03

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
