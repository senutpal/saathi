"""Sign-in history + global cookie revocation ("log out everywhere").

Revocation tests deliberately build their OWN app instances: the shared
conftest `session` fixture holds an app context open, and Flask's test
client REUSES a same-app context for every request — which means `g`
(and its cached _login_user) survives across requests and the user_loader
never runs. Real deployments resolve per request; these tests mirror that
by keeping no context open.
"""

from datetime import UTC, datetime

import pytest

from saathi import create_app
from saathi.extensions import db
from saathi.models import LoginRecord, User
from saathi.models.base import utcnow


@pytest.fixture()
def fresh(tmp_path, request):
    """(client) with schema ready and one user; no app context held open."""
    app = create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE_PATH": str(tmp_path / "revocation.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SCHEDULER_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        user = User(username="a", email="a@example.com")
        user.set_password("correct horse")
        db.session.add(user)
        db.session.commit()

    def _dispose() -> None:
        # pooled sqlite connections would otherwise be GC-closed later and
        # surface as unraisable ResourceWarnings attributed to random tests
        with app.app_context():
            for engine in db.engines.values():
                engine.dispose()

    request.addfinalizer(_dispose)
    return app.test_client()


def _invalidate(client) -> None:
    with client.application.app_context():
        User.query.filter_by(email="a@example.com").one().session_invalid_before = utcnow()
        db.session.commit()


def test_login_captures_signin_row(login, make_user, session) -> None:
    make_user()

    login("a@example.com", "correct horse")

    rows = LoginRecord.query.all()
    assert len(rows) == 1
    assert rows[0].at is not None
    assert rows[0].user_agent is not None
    # Werkzeug test clients present as IPv4/IPv6 literals, never empty
    assert rows[0].ip


def test_logout_everywhere_kills_existing_cookie(fresh) -> None:
    fresh.post("/auth/login", data={"email": "a@example.com", "password": "correct horse"})
    assert fresh.get("/").status_code == 200

    _invalidate(fresh)

    assert fresh.get("/").status_code == 302
    # a fresh login stamps a new login_ts and works again
    fresh.post("/auth/login", data={"email": "a@example.com", "password": "correct horse"})
    assert fresh.get("/").status_code == 200


def test_legacy_cookie_without_login_ts_is_rejected(fresh) -> None:
    with fresh.session_transaction() as s:
        s["_user_id"] = "1"  # pre-P13 shape: no login_ts stamp

    assert fresh.get("/").status_code == 302


def test_cookie_older_than_invalidation_stamp_is_dead(fresh) -> None:
    fresh.post("/auth/login", data={"email": "a@example.com", "password": "correct horse"})
    with fresh.session_transaction() as s:
        stale_ts = s["login_ts"]

    stamp = datetime.fromtimestamp(stale_ts + 60, tz=UTC).replace(tzinfo=None)
    with fresh.application.app_context():
        User.query.filter_by(email="a@example.com").one().session_invalid_before = stamp
        db.session.commit()

    assert fresh.get("/").status_code == 302


def test_security_page_lists_signins_and_kill_switch(logged_in_client) -> None:
    response = logged_in_client.get("/settings/security")

    assert response.status_code == 200
    assert b"Two-factor authentication" in response.data
    assert b"Log out everywhere" in response.data
    # the login that created this very session is already on the list
    assert b"127.0.0.1" in response.data or b"localhost" in response.data


def test_logout_everywhere_post_ends_this_session(logged_in_client, session) -> None:
    response = logged_in_client.post("/settings/logout-everywhere")

    assert response.status_code == 302
    assert logged_in_client.get("/").status_code == 302
