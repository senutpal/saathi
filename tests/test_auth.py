"""Auth behavior suite mapping B03 T1–T12 (adapted to P02 schema + phase decisions)."""

import pytest
from flask_login import login_required

from saathi import create_app
from saathi.config import ProductionConfig
from saathi.extensions import db
from saathi.models import ActivityLog, Profile, User
from saathi.utils import get_own_or_404, safe_next

REGISTER_DATA = {
    "username": "demo",
    "email": "demo@example.com",
    "password": "longenough1",
    "confirm": "longenough1",
}


def test_register_creates_account_and_redirects_to_login(app, client) -> None:
    response = client.post("/auth/register", data=REGISTER_DATA)

    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/login"

    with app.app_context():
        user = User.query.filter_by(email="demo@example.com").one()
        assert user.username == "demo"
        assert user.password_hash.startswith("scrypt:")
        assert ActivityLog.query.filter_by(user_id=user.id, activity_type="signup").count() == 1


def test_register_rejects_duplicate_email(client, session, make_user) -> None:
    make_user(email="dup@example.com")

    response = client.post(
        "/auth/register",
        data={**REGISTER_DATA, "username": "other", "email": "DUP@example.com"},
    )

    assert response.status_code == 200
    assert b"already exists" in response.data
    assert User.query.count() == 1


def test_register_rejects_duplicate_username(client, session, make_user) -> None:
    make_user(username="taken")

    response = client.post(
        "/auth/register",
        data={**REGISTER_DATA, "username": "taken", "email": "fresh@example.com"},
    )

    assert response.status_code == 200
    assert b"already taken" in response.data
    assert User.query.count() == 1


def test_register_rejects_short_password(client, session) -> None:
    response = client.post(
        "/auth/register", data={**REGISTER_DATA, "password": "short7", "confirm": "short7"}
    )

    assert response.status_code == 200
    assert User.query.count() == 0


def test_register_rejects_password_mismatch(client, session) -> None:
    response = client.post(
        "/auth/register",
        data={**REGISTER_DATA, "confirm": "different9"},
    )

    assert response.status_code == 200
    assert b"Passwords must match." in response.data
    assert User.query.count() == 0


def test_login_success_redirects_home_and_grants_access(make_user, login, client) -> None:
    make_user()

    response = login("a@example.com", "correct horse")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert client.get("/").status_code == 200


def test_login_wrong_password_shows_uniform_error(make_user, login) -> None:
    make_user()

    response = login("a@example.com", "wrong password")

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_unknown_email_response_is_byte_identical_to_wrong_password(make_user, client) -> None:
    make_user()

    wrong_password = client.post(
        "/auth/login", data={"email": "a@example.com", "password": "nope nope nope"}
    )
    unknown_email = client.post(
        "/auth/login", data={"email": "ghost@example.com", "password": "nope nope nope"}
    )

    assert unknown_email.status_code == wrong_password.status_code == 200
    assert unknown_email.data == wrong_password.data


def test_anonymous_dashboard_hit_preserves_next(client) -> None:
    response = client.get("/")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/auth/login")
    assert "next=" in location


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("/notes", "/notes"),
        ("/a?b=1", "/a?b=1"),
        ("//evil.com", ""),
        ("\\evil.com", ""),
        ("https://evil.com/x", ""),
        ("http://x.com", ""),
        ("relative/no-slash", ""),
        (None, ""),
        ("", ""),
    ],
)
def test_safe_next_accepts_only_site_relative_paths(target, expected) -> None:
    assert safe_next(target) == expected


def test_login_honors_safe_next_and_rejects_open_redirects(app, client, make_user) -> None:
    make_user()

    safe = client.post(
        "/auth/login",
        data={"email": "a@example.com", "password": "correct horse", "next": "/notes"},
    )

    assert safe.headers["Location"] == "/notes"

    fresh = app.test_client()
    evil = fresh.post(
        "/auth/login",
        data={"email": "a@example.com", "password": "correct horse", "next": "//evil.com"},
    )

    assert evil.headers["Location"] == "/"


def test_logout_is_post_only_and_ends_session(client, make_user, login) -> None:
    make_user()
    login("a@example.com", "correct horse")

    assert client.get("/auth/logout").status_code == 405

    response = client.post("/auth/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert client.get("/").status_code == 302


def test_authed_visitors_bounce_off_auth_pages(client, make_user, login) -> None:
    make_user()
    login("a@example.com", "correct horse")

    assert client.get("/auth/login").headers["Location"] == "/"
    assert client.get("/auth/register").headers["Location"] == "/"


def test_get_own_or_404_hides_foreign_rows(app, client, session) -> None:
    @app.get("/_ownership-probe/<int:profile_id>")
    @login_required
    def _ownership_probe(profile_id: int) -> str:
        get_own_or_404(Profile, profile_id)
        return "ok"

    owner = User(username="owner", email="owner@example.com")
    owner.set_password("pw eight 8")
    intruder = User(username="intruder", email="intruder@example.com")
    intruder.set_password("pw eight 8")
    db.session.add_all([owner, intruder])
    db.session.commit()
    db.session.add_all(
        [
            Profile(user_id=owner.id, full_name="Owner A"),
            Profile(user_id=intruder.id, full_name="Intruder B"),
        ]
    )
    db.session.commit()
    owner_profile_id = Profile.query.filter_by(user_id=owner.id).one().id

    login_response = client.post(
        "/auth/login", data={"email": "intruder@example.com", "password": "pw eight 8"}
    )
    assert login_response.status_code == 302

    assert client.get(f"/_ownership-probe/{owner_profile_id}").status_code == 404
    own_profile_id = Profile.query.filter_by(user_id=intruder.id).one().id
    assert client.get(f"/_ownership-probe/{own_profile_id}").status_code == 200


def test_tokenless_post_is_rejected_when_csrf_enabled(tmp_path) -> None:
    fresh = create_app(
        test_config={
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "csrf.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SCHEDULER_ENABLED": False,
            # test_config always layers over TestingConfig, which disables CSRF;
            # re-enable to prove the DEFAULT config enforces it (B03 T12).
            "WTF_CSRF_ENABLED": True,
        }
    )
    client = fresh.test_client()

    response = client.post("/auth/login", data={"email": "x@y.com", "password": "whatever1"})

    assert response.status_code == 400


def test_session_cookie_flags_hardened(app) -> None:
    assert app.config["SESSION_COOKIE_NAME"] == "_saathi_session"
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert not app.config.get("SESSION_COOKIE_SECURE", False)
    assert ProductionConfig.SESSION_COOKIE_SECURE is True


def test_rate_limit_blocks_sixth_login_post(tmp_path) -> None:
    fresh = create_app(
        test_config={
            "TESTING": True,
            "RATELIMIT_ENABLED": True,
            "DATABASE_PATH": str(tmp_path / "rl.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "SCHEDULER_ENABLED": False,
        }
    )
    with fresh.app_context():
        db.create_all()
        user = User(username="bruteforce", email="bf@example.com")
        user.set_password("right password 8")
        db.session.add(user)
        db.session.commit()
    client = fresh.test_client()

    statuses = [
        client.post(
            "/auth/login", data={"email": "bf@example.com", "password": "wrong password"}
        ).status_code
        for _ in range(6)
    ]

    with fresh.app_context():
        for engine in db.engines.values():
            engine.dispose()

    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert statuses[5] == 429
