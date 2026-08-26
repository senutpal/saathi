"""TOTP 2FA behavior: enable roundtrip, backup codes, lockout interplay."""

import time

import pyotp
import pytest

from saathi.extensions import db
from saathi.models import BackupCode, User
from saathi.models.base import utcnow
from saathi.services import lockout, twofa

TWO_FA_PATH = "/auth/login/two-fa"
LOGIN = {"email": "a@example.com", "password": "correct horse"}


@pytest.fixture()
def enabled_user(session, make_user):
    """A user with 2FA already confirmed on."""
    make_user()
    user = User.query.filter_by(email="a@example.com").one()
    user.totp_secret = pyotp.random_base32()
    user.twofa_enabled = True
    db.session.commit()
    return user


def _code(secret: str) -> str:
    return pyotp.TOTP(secret).now()


def test_enable_stores_secret_but_stays_off(logged_in_client, session) -> None:
    response = logged_in_client.post("/settings/two-fa/enable")

    assert response.status_code == 200
    assert b"data:image/svg" in response.data
    user = User.query.filter_by(email="a@example.com").one()
    assert user.totp_secret  # stored pre-confirm (crash-safe)
    assert user.twofa_enabled is False


def test_confirm_with_live_code_flips_on_and_mints_ten_codes(logged_in_client, session) -> None:
    logged_in_client.post("/settings/two-fa/enable")
    user = User.query.filter_by(email="a@example.com").one()
    secret = user.totp_secret

    response = logged_in_client.post("/settings/two-fa/confirm", data={"code": _code(secret)})

    assert b"shown only once" in response.data
    user = User.query.filter_by(email="a@example.com").one()
    assert user.twofa_enabled is True
    assert BackupCode.query.count() == 10


def test_confirm_bad_code_rerenders_setup_then_restarts_after_five(logged_in_client) -> None:
    logged_in_client.post("/settings/two-fa/enable")
    for _ in range(1, 5):
        response = logged_in_client.post("/settings/two-fa/confirm", data={"code": "000000"})
        assert response.status_code == 200  # setup page again
        user = User.query.filter_by(email="a@example.com").one()
        assert user.twofa_enabled is False
        assert user.totp_secret  # unchanged secret keeps the scanned QR valid

    response = logged_in_client.post(
        "/settings/two-fa/confirm", data={"code": "000000"}, follow_redirects=True
    )
    user = User.query.filter_by(email="a@example.com").one()
    assert user.totp_secret is None  # burned -> setup restarts
    assert b"restarted" in response.data


def test_password_alone_lands_on_challenge_not_dashboard(enabled_user, client) -> None:
    response = client.post("/auth/login", data=LOGIN)

    assert response.status_code == 302
    assert response.headers["Location"] == TWO_FA_PATH
    # half-session is NOT a session: the dashboard stays locked
    assert client.get("/").status_code == 302


def test_valid_totp_completes_signin(enabled_user, client) -> None:
    client.post("/auth/login", data=LOGIN)

    done = client.post(TWO_FA_PATH, data={"code": _code(enabled_user.totp_secret)})

    assert done.status_code == 302
    assert client.get("/").status_code == 200


def test_wrong_totp_counts_toward_lockout(enabled_user, client, session) -> None:
    client.post("/auth/login", data=LOGIN)
    for _ in range(5):
        response = client.post(TWO_FA_PATH, data={"code": "000000"})
        assert response.status_code == 200
        # apostrophe renders escaped; match the stable prefix
        assert b"code didn" in response.data

    assert lockout.is_locked("a@example.com")
    # even a correct password can no longer reach the challenge
    bounced = client.post("/auth/login", data=LOGIN)
    assert bounced.status_code == 200
    assert b"Invalid email or password" in bounced.data


def test_lockout_window_expiry_restores_the_challenge(enabled_user, client, session) -> None:
    from saathi.models import LoginAttempt

    client.post("/auth/login", data=LOGIN)
    for _ in range(5):
        client.post(TWO_FA_PATH, data={"code": "000000"})
    stale = utcnow() - 2 * lockout.LOCKOUT_WINDOW
    for row in LoginAttempt.query.all():
        row.attempted_at = stale
    db.session.commit()

    client.post("/auth/login", data=LOGIN)
    done = client.post(TWO_FA_PATH, data={"code": _code(enabled_user.totp_secret)})
    assert done.status_code == 302
    assert client.get("/").status_code == 200


def test_backup_code_single_use_then_next_code(enabled_user, client, session) -> None:
    codes = twofa.generate_backup_codes()
    twofa.store_backup_codes(enabled_user, codes)
    db.session.commit()

    client.post("/auth/login", data=LOGIN)
    spent = client.post(TWO_FA_PATH, data={"code": codes[0].lower()})
    assert spent.status_code == 302  # case-insensitive acceptance

    client.post("/auth/logout")
    client.post("/auth/login", data=LOGIN)
    replay = client.post(TWO_FA_PATH, data={"code": codes[0]})
    assert b"code didn" in replay.data  # single-use holds

    second = client.post(TWO_FA_PATH, data={"code": codes[1]})
    assert second.status_code == 302


def test_regenerate_voids_the_old_set(logged_in_client, session) -> None:
    logged_in_client.post("/settings/two-fa/enable")
    logged_in_client.post(
        "/settings/two-fa/confirm",
        data={"code": _code(User.query.filter_by(email="a@example.com").one().totp_secret)},
    )
    old_hashes = {row.code_hash for row in BackupCode.query.all()}

    response = logged_in_client.post("/settings/two-fa/backup-codes/regenerate")

    assert b"shown only once" in response.data
    rows = BackupCode.query.all()
    assert len(rows) == 10
    assert {row.code_hash for row in rows}.isdisjoint(old_hashes)


def test_disable_needs_password_and_code(logged_in_client, session) -> None:
    user_row = User.query.filter_by(email="a@example.com").one()
    user_row.totp_secret = pyotp.random_base32()
    user_row.twofa_enabled = True
    db.session.commit()
    secret = user_row.totp_secret

    url = "/settings/two-fa/disable"
    logged_in_client.post(url, data={"password": "correct horse", "code": ""})
    assert User.query.filter_by(email="a@example.com").one().twofa_enabled is True

    logged_in_client.post(url, data={"password": "correct horse", "code": "000000"})
    assert User.query.filter_by(email="a@example.com").one().twofa_enabled is True

    logged_in_client.post(url, data={"password": "nope nope nope", "code": _code(secret)})
    assert User.query.filter_by(email="a@example.com").one().twofa_enabled is True

    logged_in_client.post(url, data={"password": "correct horse", "code": _code(secret)})
    user = User.query.filter_by(email="a@example.com").one()
    assert user.twofa_enabled is False
    assert user.totp_secret is None
    assert BackupCode.query.count() == 0


def test_disable_via_backup_code_succeeds(logged_in_client, session) -> None:
    user_row = User.query.filter_by(email="a@example.com").one()
    user_row.totp_secret = pyotp.random_base32()
    user_row.twofa_enabled = True
    db.session.commit()
    codes = twofa.generate_backup_codes()
    twofa.store_backup_codes(user_row, codes)
    db.session.commit()

    logged_in_client.post(
        "/settings/two-fa/disable", data={"password": "correct horse", "code": codes[3]}
    )

    user = User.query.filter_by(email="a@example.com").one()
    assert user.twofa_enabled is False
    assert BackupCode.query.count() == 0


def test_pre_2fa_stash_expires(monkeypatch, enabled_user, client) -> None:
    client.post("/auth/login", data=LOGIN)

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 301)

    assert client.get(TWO_FA_PATH).headers["Location"] == "/auth/login"


def test_totp_verify_window_is_one_step_not_more(session, make_user) -> None:
    """valid_window=1 exactly: two steps old must fail (B16 pitfall)."""
    make_user()
    user = User.query.filter_by(email="a@example.com").one()
    user.twofa_enabled = True
    user.totp_secret = pyotp.random_base32()
    db.session.commit()

    totp = pyotp.TOTP(user.totp_secret)
    two_steps_ago = totp.at(int(time.time()) - 61)

    assert twofa.verify_login_code(user, two_steps_ago) is False
