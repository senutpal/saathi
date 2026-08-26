"""Lockout ledger behavior: window counting, uniform locked body, expiry."""

from datetime import UTC, datetime, timedelta

from saathi.extensions import db
from saathi.models import LoginAttempt
from saathi.models.base import utcnow
from saathi.services import lockout


def seed_failures(email: str, count: int, *, at: datetime | None = None) -> None:
    stamp = at or utcnow()
    for _ in range(count):
        db.session.add(LoginAttempt(email=email, attempted_at=stamp, success=False))
    db.session.commit()


def test_four_failures_still_allow_correct_password(make_user, login) -> None:
    make_user()
    seed_failures("a@example.com", 4)

    assert login("a@example.com", "correct horse").status_code == 302


def test_fifth_failure_locks_even_with_correct_password(make_user, login, client) -> None:
    make_user()
    seed_failures("a@example.com", 5)

    response = login("a@example.com", "correct horse")

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data
    # never logged in despite the correct password
    assert client.get("/").status_code == 302


def test_locked_body_is_byte_identical_to_wrong_password_body(make_user, client) -> None:
    make_user()

    wrong_password = client.post(
        "/auth/login", data={"email": "a@example.com", "password": "nope nope nope"}
    )
    seed_failures("a@example.com", 5)
    locked = client.post(
        "/auth/login", data={"email": "a@example.com", "password": "correct horse"}
    )

    assert locked.status_code == wrong_password.status_code == 200
    assert locked.data == wrong_password.data


def test_unknown_email_attempts_land_in_the_ledger(client, session) -> None:
    client.post("/auth/login", data={"email": "Ghost@Example.com", "password": "whatever9"})

    attempts = LoginAttempt.query.all()
    assert len(attempts) == 1
    assert attempts[0].email == "ghost@example.com"
    assert attempts[0].success is False


def test_success_clears_the_emails_failures(make_user, login) -> None:
    make_user()
    seed_failures("a@example.com", 4)

    login("a@example.com", "correct horse")

    assert LoginAttempt.query.count() == 0


def test_window_expiry_unlocks_login(make_user, login) -> None:
    make_user()
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=16)
    seed_failures("a@example.com", 5, at=stale)

    assert not lockout.is_locked("a@example.com")
    assert login("a@example.com", "correct horse").status_code == 302


def test_counting_ignores_case_and_whitespace() -> None:
    assert lockout.normalize("  A@Example.COM ") == "a@example.com"


def test_prune_deletes_only_stale_rows(session) -> None:
    now = utcnow()
    db.session.add(LoginAttempt(email="old@example.com", attempted_at=now - timedelta(days=31)))
    db.session.add(LoginAttempt(email="new@example.com", attempted_at=now - timedelta(days=1)))
    db.session.commit()

    removed = lockout.prune_old_attempts()

    assert removed == 1
    assert LoginAttempt.query.filter_by(email="old@example.com").count() == 0
    assert LoginAttempt.query.filter_by(email="new@example.com").count() == 1
