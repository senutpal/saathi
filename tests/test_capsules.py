"""Time capsule suite: exact-boundary reveal, sealed secrecy, form guards."""

from __future__ import annotations

from datetime import datetime, timedelta

import saathi.services.daily as daily
from saathi.extensions import db
from saathi.models import CapsuleMessage, Notification, User


def _make_capsule(user_id: int, *, open_at: datetime, title: str = "Dear me") -> CapsuleMessage:
    capsule = CapsuleMessage(
        user_id=user_id,
        title=title,
        body="The secret of the universe: 42.",
        open_at=open_at,
    )
    db.session.add(capsule)
    db.session.commit()
    return capsule


def _login_as(client, login, email: str) -> None:
    client.post("/auth/logout")
    login(email, "correct horse")


def test_capsule_flips_exactly_at_boundary(session, make_user) -> None:
    user = make_user()
    boundary = datetime(2026, 9, 1, 12, 0)
    capsule = _make_capsule(user.id, open_at=boundary)

    daily.open_due_capsules(now_fn=lambda: boundary - timedelta(minutes=1))
    assert db.session.get(CapsuleMessage, capsule.id).status == "sealed"

    daily.open_due_capsules(now_fn=lambda: boundary + timedelta(minutes=1))
    assert db.session.get(CapsuleMessage, capsule.id).status == "opened"

    notifications = db.session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].title == "A message from your past self"
    assert notifications[0].event_id is None

    daily.open_due_capsules(now_fn=lambda: boundary + timedelta(days=5))
    assert db.session.query(Notification).count() == 1


def test_sealed_body_never_reaches_html(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    capsule = _make_capsule(user.id, open_at=datetime(2100, 1, 1, 9, 0), title="Future money plan")

    response = logged_in_client.get(f"/capsules/{capsule.id}")

    assert response.status_code == 200
    assert "Still sealed" in response.get_data(as_text=True)
    assert "secret of the universe" not in response.get_data(as_text=True)


def test_opened_capsule_shows_letter_with_dates(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    capsule = _make_capsule(user.id, open_at=datetime(2020, 1, 1, 12, 0), title="Old letter")
    capsule.status = "opened"
    db.session.commit()

    body = logged_in_client.get(f"/capsules/{capsule.id}").get_data(as_text=True)

    assert "Written by you on" in body
    assert "secret of the universe" in body


def test_foreign_capsule_is_404(client, make_user, login, session) -> None:
    owner = make_user(username="owner", email="o@example.com")
    capsule = _make_capsule(owner.id, open_at=datetime(2026, 1, 1, 9, 0))
    make_user(username="bee", email="b@example.com")

    _login_as(client, login, "b@example.com")

    assert client.get(f"/capsules/{capsule.id}").status_code == 404


def test_create_happy_path_seals_with_audit(logged_in_client, session) -> None:
    from saathi.models import ActivityLog

    response = logged_in_client.post(
        "/capsules/new",
        data={
            "title": "Graduation note",
            "body": "You made it.",
            "open_at": "2030-08-01T09:00",
            "submit": True,
        },
        follow_redirects=True,
    )

    capsule = db.session.query(CapsuleMessage).one()
    assert capsule.status == "sealed"
    assert capsule.title == "Graduation note"
    audit = db.session.query(ActivityLog).filter_by(activity_type="capsule_sealed").one()
    assert audit is not None
    assert "Sealed" in response.get_data(as_text=True)


def test_past_open_date_rejected(logged_in_client, session) -> None:
    logged_in_client.post(
        "/capsules/new",
        data={
            "title": "Too late",
            "body": "body",
            "open_at": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "submit": True,
        },
    )

    assert db.session.query(CapsuleMessage).count() == 0


def test_inside_one_hour_horizon_rejected(logged_in_client, session) -> None:
    logged_in_client.post(
        "/capsules/new",
        data={
            "title": "Soon",
            "body": "body",
            "open_at": (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M"),
            "submit": True,
        },
    )

    assert db.session.query(CapsuleMessage).count() == 0


def test_index_lists_capsules(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    _make_capsule(user.id, open_at=datetime(2100, 1, 1, 9, 0), title="Far future")

    body = logged_in_client.get("/capsules").get_data(as_text=True)

    assert "Far future" in body
