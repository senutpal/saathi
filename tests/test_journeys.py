import datetime

import pytest

from saathi.models import (
    CapsuleMessage,
    Contact,
    Event,
    Expense,
    Habit,
    Mood,
    Note,
)
from saathi.services.scheduler import scan_and_fire


class FakeClock:
    def __init__(self, start: datetime.datetime):
        self.now = start

    def __call__(self) -> datetime.datetime:
        return self.now

    def advance(self, **kwargs):
        self.now += datetime.timedelta(**kwargs)


def test_t100_register_login_create_reminder_fire_bell_logout(client, app, session):
    resp = client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password",
            "confirm": "password",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    resp = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "password"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]
    clock = FakeClock(datetime.datetime(2030, 1, 1, 12, 0, 0))
    resp = client.post(
        "/events/create",
        data={
            "title": "My Test Reminder",
            "description": "Don't forget",
            "event_at": "2030-01-01T14:00",
            "repeat_rule": "none",
            "alert_lead_minutes": "30",
        },
        follow_redirects=True,
    )
    assert b"Reminder created" in resp.data
    with app.app_context():
        clock.advance(minutes=105)
        scan_and_fire(now_fn=clock)
    resp = client.get("/")
    assert b"unread" in resp.data.lower() or b"notification" in resp.data.lower()
    resp = client.post("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_t101_login_note_tags_search_history_cv(logged_in_client, session):
    client = logged_in_client
    resp = client.post(
        "/notes/new",
        data={
            "title": "Journey Note",
            "body": "Hello World",
            "tags": "journey, test",
            "event_id": "0",
        },
        follow_redirects=True,
    )
    assert b"Journey Note" in resp.data
    resp = client.get("/notes?q=Journey")
    assert b"Journey Note" in resp.data
    resp = client.get("/history")
    assert b"note_created" in resp.data or b"Journey Note" in resp.data
    resp = client.post(
        "/profile/edit",
        data={"full_name": "Test User", "title": "Dev", "bio": "Hello"},
        follow_redirects=True,
    )
    resp = client.post(
        "/profile/education/new",
        data={
            "institution": "MIT",
            "qualification": "BSc",
            "start_date": "2010-09-01",
            "end_date": "2014-06-01",
            "description": "CS",
        },
        follow_redirects=True,
    )
    resp = client.get("/profile/cv")
    assert resp.status_code == 200
    assert b"MIT" in resp.data or b"BSc" in resp.data


@pytest.mark.parametrize(
    "model_cls, create_data, route_prefix",
    [
        (
            Event,
            {"title": "A", "event_at": datetime.datetime(2030, 1, 1), "status": "scheduled"},
            "/events",
        ),
        (Note, {"title": "A", "content": "A"}, "/notes"),
        (Contact, {"name": "A"}, "/contacts"),
        (Habit, {"name": "A"}, "/habits"),
        (
            Expense,
            {"amount_cents": 1000, "category": "A", "spent_on": datetime.date(2030, 1, 1)},
            "/expenses",
        ),
        (Mood, {"score": 3, "mood_date": datetime.date(2030, 1, 1)}, "/mood"),
        (
            CapsuleMessage,
            {"title": "A", "body": "A", "open_at": datetime.datetime(2030, 1, 1)},
            "/capsules",
        ),
    ],
)
def test_t102_idor_sweep(client, app, session, make_user, model_cls, create_data, route_prefix):
    user_a = make_user(email="a@example.com", username="a", password="password")
    make_user(email="b@example.com", username="b", password="password")
    with app.app_context():
        obj = model_cls(user_id=user_a.id, **create_data)
        session.add(obj)
        session.commit()
        obj_id = obj.id
    client.post("/auth/login", data={"email": "b@example.com", "password": "password"})
    resp = client.get(f"{route_prefix}/{obj_id}/edit")
    assert resp.status_code == 404
    resp = client.post(f"{route_prefix}/{obj_id}/delete")
    assert resp.status_code == 404
