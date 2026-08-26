"""App factory for the Saathi personal-assistant web app."""

import os
from pathlib import Path

from flask import Flask, flash, render_template, request
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
    from .blueprints import (
        auth,
        contacts,
        events,
        expenses,
        files,
        habits,
        history,
        main,
        mood,
        notes,
        notifications,
        profile,
        search,
    )

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(profile.bp)
    app.register_blueprint(events.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(notes.bp)
    app.register_blueprint(files.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(history.bp)
    app.register_blueprint(contacts.bp)
    app.register_blueprint(habits.bp)
    app.register_blueprint(mood.bp)
    app.register_blueprint(expenses.bp)


def register_error_handlers(app: Flask) -> None:
    def render(code: int):
        return render_template(f"errors/{code}.html"), code

    def too_large(_err):
        # the aborted multipart parse leaves werkzeug's spooled temp file open
        # (unraisable ResourceWarning on Windows); the CSRF token is already
        # consumed, so flash survives via the session while the 413 status
        # stays honest for tests/clients
        request.close()
        flash("That file is larger than the 5 MB limit.", "error")
        return render(413)

    app.register_error_handler(403, lambda _err: render(403))
    app.register_error_handler(404, lambda _err: render(404))
    app.register_error_handler(413, too_large)
    app.register_error_handler(429, lambda _err: render(429))
    app.register_error_handler(RateLimitExceeded, lambda _err: render(429))
    app.register_error_handler(500, lambda _err: render(500))


def register_template_helpers(app: Flask) -> None:
    from . import utils
    from .blueprints import notifications
    from .services.markdown import excerpt, highlight, render_md
    from .services.money import format_cents

    app.jinja_env.filters["ist"] = utils.ist_format
    app.jinja_env.filters["md"] = render_md
    app.jinja_env.filters["excerpt"] = excerpt
    app.jinja_env.filters["highlight"] = highlight
    app.jinja_env.filters["money"] = format_cents
    app.context_processor(notifications.bell_context)


def _start_scheduler(app: Flask) -> None:
    # The debug reloader runs parent+child; only the reloader child may tick.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from .services.scheduler import start_ticker

        start_ticker(app)


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
    _start_scheduler(app)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    _log_startup(app)
    return app
