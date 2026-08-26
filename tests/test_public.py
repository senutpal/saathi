"""Public share card: opt-in privacy, uniform 404s, QR wiring."""

from __future__ import annotations

import secrets
from datetime import date

from saathi.extensions import db
from saathi.models import EducationEntry, Profile


def _minted_token() -> str:
    return "tok-" + secrets.token_urlsafe(8)


def _seed_profile(user_id: int, *, enabled: bool) -> str:
    token = _minted_token()
    db.session.add(
        Profile(
            user_id=user_id,
            full_name="Ada Lovelace",
            phone="555-1234",
            address="12 Analytical St",
            date_of_birth=date(1815, 12, 10),
            likes="poetry, engines",
            public_token=token,
            share_enabled=enabled,
        )
    )
    db.session.commit()
    return token


def _seed_entries(user_id: int) -> None:
    db.session.add(
        EducationEntry(
            user_id=user_id,
            institution="Analytical Engines Ltd",
            qualification="BSc",
            field_of_study="Computing",
        )
    )
    db.session.commit()


def test_valid_token_with_sharing_disabled_is_404(client, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    _seed_entries(alice.id)
    token = _seed_profile(alice.id, enabled=False)

    assert client.get(f"/u/{token}").status_code == 404


def test_random_token_is_404(client):
    assert client.get("/u/never-minted-token").status_code == 404


def test_enabled_card_hides_all_contact_fields(client, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    _seed_entries(alice.id)
    token = _seed_profile(alice.id, enabled=True)

    page = client.get(f"/u/{token}").get_data(as_text=True)

    for marker in ("Ada Lovelace", "poetry", "Analytical Engines Ltd"):
        assert marker in page
    for secret in ("555-1234", "12 Analytical St", "1815"):
        assert secret not in page


def test_regenerate_kills_previous_link(logged_in_client):
    logged_in_client.post("/profile/share")
    old = db.session.query(Profile).first().public_token
    logged_in_client.post("/profile/share/regenerate")
    new = db.session.query(Profile).first().public_token

    assert old != new
    assert logged_in_client.get(f"/u/{old}").status_code == 404
    assert logged_in_client.get(f"/u/{new}").status_code == 200


def test_disable_turns_live_link_into_404(logged_in_client):
    logged_in_client.post("/profile/share")
    profile = db.session.query(Profile).first()
    live = profile.public_token
    logged_in_client.post("/profile/share")
    profile = db.session.query(Profile).first()

    assert logged_in_client.get(f"/u/{live}").status_code == 404
    assert profile.public_token == live  # token kept; sharing gate flips off


def test_anonymous_visitor_sees_enabled_card(app, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    token = _seed_profile(alice.id, enabled=True)

    anon = app.test_client()
    page = anon.get(f"/u/{token}")

    assert page.status_code == 200
    assert "Ada Lovelace" in page.get_data(as_text=True)


def test_first_enable_mints_token_and_qr_appears_on_profile(logged_in_client):
    assert b"data:image/svg+xml" not in logged_in_client.get("/profile").data

    logged_in_client.post("/profile/share")

    page = logged_in_client.get("/profile").get_data(as_text=True)
    profile = db.session.query(Profile).first()
    assert profile.share_enabled is True and profile.public_token is not None
    assert "data:image/svg+xml" in page
