"""App factory for the Saathi personal-assistant web app."""

import os
from pathlib import Path

from flask import Flask, render_template
from flask_limiter.errors import RateLimitExceeded

from .config import BASE_DIR, MAP
from .extensions import init_db, init_extensions


def _resolve_relative(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


def _configure_storage(app: Flask) -> None:
    if app.config["SAATHI_ENV"] == "production":
        secret = os.environ.get("SECRET_KEY", "")
        if len(secret) < 32 or secret == "dev-not-for-prod":
            raise RuntimeError("SECRET_KEY env var must be >=32 chars when FLASK_ENV=production")
        app.config["SECRET_KEY"] = secret
    db_path = _resolve_relative(str(app.config["DATABASE_PATH"]))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE_PATH"] = str(db_path)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"
    upload_dir = _resolve_relative(str(app.config["UPLOAD_FOLDER"]))
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_dir)


def register_blueprints(app: Flask) -> None:
    from .blueprints import auth, main

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)


def register_error_handlers(app: Flask) -> None:
    def render(code: int):
        return render_template(f"errors/{code}.html"), code

    app.register_error_handler(403, lambda _err: render(403))
    app.register_error_handler(404, lambda _err: render(404))
    app.register_error_handler(429, lambda _err: render(429))
    app.register_error_handler(RateLimitExceeded, lambda _err: render(429))
    app.register_error_handler(500, lambda _err: render(500))


def register_template_helpers(app: Flask) -> None:
    """Hook point where later phases register Jinja filters and globals."""


def _log_startup(app: Flask) -> None:
    app.logger.info(
        "saathi up env=%s db=%s uploads=%s tz=%s max_upload_mb=%s scheduler=%s",
        app.config["SAATHI_ENV"],
        app.config["DATABASE_PATH"],
        app.config["UPLOAD_FOLDER"],
        app.config["TIMEZONE"],
        app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
        app.config["SCHEDULER_ENABLED"],
    )


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    selected = "test" if test_config else os.environ.get("SAATHI_CONFIG", "dev")
    app.config.from_object(MAP[selected])
    app.config.from_pyfile("config.py", silent=True)
    if test_config:
        app.config.update(test_config)

    _configure_storage(app)
    init_extensions(app)
    init_db(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_template_helpers(app)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    _log_startup(app)
    return app
