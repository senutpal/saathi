"""Profile CRUD and CV generation suite (phase P04)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from saathi.extensions import db
from saathi.models import Profile


def _profile_count(session: Session) -> int:
    return len(db.session.query(Profile).all())


def test_profile_requires_login(client) -> None:
    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")
    assert "next=/profile" in response.headers["Location"]


def test_profile_view_renders_for_authed_user(logged_in_client) -> None:
    response = logged_in_client.get("/profile")

    assert response.status_code == 200
    assert b"No profile yet" in response.data


def test_edit_get_renders_empty_form(logged_in_client) -> None:
    response = logged_in_client.get("/profile/edit")

    assert response.status_code == 200
    assert b"Save profile" in response.data


def test_edit_post_creates_profile_row(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Ada Lovelace",
            "headline": "Analyst & metaphysician",
            "phone": "+91 98765 43210",
            "skills_csv": "Math, Python",
            "summary": "Pioneer of computing.",
        },
    )

    assert response.status_code == 302
    row = db.session.query(Profile).one()
    assert row.full_name == "Ada Lovelace"
    assert row.phone == "+91 98765 43210"


def test_edit_post_updates_existing_row_without_duplicating(logged_in_client, session) -> None:
    logged_in_client.post("/profile/edit", data={"full_name": "Ada Lovelace"})
    response = logged_in_client.post("/profile/edit", data={"full_name": "A. King"})

    assert response.status_code == 302
    rows = db.session.query(Profile).all()
    assert len(rows) == 1
    assert rows[0].full_name == "A. King"


def test_edit_prefills_existing_values(logged_in_client, session) -> None:
    logged_in_client.post("/profile/edit", data={"full_name": "Ada Lovelace"})

    response = logged_in_client.get("/profile/edit")

    assert b'value="Ada Lovelace"' in response.data


def test_future_date_of_birth_rejected(logged_in_client, session) -> None:
    future = (date.today() + timedelta(days=30)).isoformat()
    response = logged_in_client.post(
        "/profile/edit", data={"full_name": "Time Traveller", "date_of_birth": future}
    )

    assert response.status_code == 200
    assert b"cannot be in the future" in response.data
    assert _profile_count(session) == 0


def test_pre_1900_date_of_birth_rejected(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/profile/edit", data={"full_name": "Ancient One", "date_of_birth": "1899-12-31"}
    )

    assert response.status_code == 200
    assert b"1900 or later" in response.data
    assert _profile_count(session) == 0


def test_phone_with_letters_rejected(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/profile/edit", data={"full_name": "Ada Lovelace", "phone": "call me maybe"}
    )

    assert response.status_code == 200
    assert b"digits, spaces and + - ( ) . only" in response.data
    assert _profile_count(session) == 0


def test_summary_over_2000_chars_rejected(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/profile/edit",
        data={"full_name": "Ada Lovelace", "summary": "x" * 2001},
    )

    assert response.status_code == 200
    assert _profile_count(session) == 0


def test_valid_phone_with_punctuation_accepted(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/profile/edit",
        data={"full_name": "Ada Lovelace", "phone": "+91 (080) 2266-0320."},
    )

    assert response.status_code == 302
