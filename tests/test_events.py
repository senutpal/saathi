"""Events CRUD suite: IST boundaries, ownership, day agenda, month grid."""

from __future__ import annotations

from datetime import datetime, timedelta

from saathi.extensions import db
from saathi.models import ActivityLog, Event, Notification, User
from saathi.models.base import utcnow
from saathi.services.agenda import month_grid
from saathi.services.scheduler import scan_and_fire
from saathi.utils import ist_to_utc_naive, utc_to_ist_wall


def _wall(days_ahead: int) -> str:
    """A guaranteed-future/past IST datetime-local string for form posts."""
    return utc_to_ist_wall(utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M")


def _post_event(client, *, days_ahead: int = 1, title: str | None = "Dentist"):
    data = {
        "title": title,
        "event_at": _wall(days_ahead),
        "repeat_rule": "none",
        "alert_lead_minutes": "30",
    }
    if title is None:
        del data["title"]
    return client.post("/events/create", data=data)


def _seed(user_id: int, *, event_at: datetime, title: str = "Seeded", **kwargs) -> Event:
    event = Event(user_id=user_id, title=title, event_at=event_at, **kwargs)
    db.session.add(event)
    db.session.commit()
    return event


def _sole_user() -> User:
    return db.session.query(User).one()


def test_events_require_login(client) -> None:
    response = client.get("/events")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_create_get_renders_empty_form(logged_in_client) -> None:
    response = logged_in_client.get("/events/create")

    assert response.status_code == 200
    assert b"Save reminder" in response.data


def test_create_post_stores_naive_utc(logged_in_client, session) -> None:
    wall = _wall(1)
    expected_utc = ist_to_utc_naive(datetime.strptime(wall, "%Y-%m-%dT%H:%M"))

    response = logged_in_client.post(
        "/events/create",
        data={
            "title": "Dentist",
            "event_at": wall,
            "repeat_rule": "none",
            "alert_lead_minutes": "30",
        },
    )

    assert response.status_code == 302
    row = db.session.query(Event).one()
    assert row.title == "Dentist"
    assert row.event_at == expected_utc
    assert row.status == "scheduled"


def test_create_rejects_past_time_inline(logged_in_client, session) -> None:
    response = _post_event(logged_in_client, days_ahead=-1)

    assert response.status_code == 200
    assert b"must be in the future" in response.data
    assert db.session.query(Event).count() == 0


def test_create_requires_title(logged_in_client, session) -> None:
    response = _post_event(logged_in_client, title=None)

    assert response.status_code == 200
    assert db.session.query(Event).count() == 0


def test_title_over_one_hundred_twenty_chars_rejected(logged_in_client, session) -> None:
    response = _post_event(logged_in_client, title="x" * 121)

    assert response.status_code == 200
    assert db.session.query(Event).count() == 0


def test_index_lists_upcoming_above_past(logged_in_client, session) -> None:
    user = _sole_user()
    _seed(user.id, event_at=utcnow() - timedelta(hours=1), title="Old news", status="fired")
    _seed(user.id, event_at=utcnow() + timedelta(days=3), title="Future plan")

    page = logged_in_client.get("/events").data.decode()

    assert page.index("Future plan") < page.index("Old news")


def test_edit_updates_scheduled_event(logged_in_client, session) -> None:
    user = _sole_user()
    event = _seed(user.id, event_at=utcnow() + timedelta(days=2))
    new_wall = _wall(5)

    response = logged_in_client.post(
        f"/events/{event.id}/edit",
        data={"title": "Renamed", "event_at": new_wall, "repeat_rule": "weekly"},
    )

    assert response.status_code == 302
    db.session.expire_all()
    refreshed = db.session.get(Event, event.id)
    assert refreshed.title == "Renamed"
    assert refreshed.repeat_rule == "weekly"
    assert refreshed.event_at == ist_to_utc_naive(datetime.strptime(new_wall, "%Y-%m-%dT%H:%M"))


def test_edit_of_fired_event_is_404(logged_in_client, session) -> None:
    user = _sole_user()
    event = _seed(user.id, event_at=utcnow() - timedelta(minutes=1), status="fired")

    assert logged_in_client.get(f"/events/{event.id}/edit").status_code == 404


def test_cancelled_event_keeps_row_and_skips_scan(logged_in_client, session) -> None:
    user = _sole_user()
    event = _seed(user.id, event_at=utcnow() - timedelta(minutes=1))

    cancel_response = logged_in_client.post(f"/events/{event.id}/cancel")
    fired = scan_and_fire()

    assert cancel_response.status_code == 302
    assert fired == 0
    db.session.expire_all()
    assert db.session.get(Event, event.id).status == "cancelled"
    assert db.session.query(Notification).count() == 0


def test_delete_removes_row(logged_in_client, session) -> None:
    user = _sole_user()
    event = _seed(user.id, event_at=utcnow() + timedelta(days=1))

    assert logged_in_client.post(f"/events/{event.id}/delete").status_code == 302
    assert db.session.query(Event).count() == 0


def test_foreign_event_reads_and_mutations_are_404(client, make_user, session) -> None:
    owner = make_user(username="owner", email="owner@example.com")
    event = _seed(owner.id, event_at=utcnow() + timedelta(days=1))
    make_user(username="intruder", email="intruder@example.com", password="other-pass-123")
    client.post("/auth/login", data={"email": "intruder@example.com", "password": "other-pass-123"})
    event_day = utc_to_ist_wall(event.event_at).strftime("%Y-%m-%d")

    get_response = client.get(f"/events/{event.id}/edit")
    cancel_response = client.post(f"/events/{event.id}/cancel")
    delete_response = client.post(f"/events/{event.id}/delete")
    day_response = client.get(f"/events/day?date={event_day}")

    assert get_response.status_code == 404
    assert cancel_response.status_code == 404
    assert delete_response.status_code == 404
    assert b"Seeded" not in day_response.data


def test_day_agenda_groups_on_ist_midnight(logged_in_client, session) -> None:
    # 01:00 IST on 2027-05-10 is 19:30 UTC on 2027-05-09 — must land on the 10th.
    user = _sole_user()
    _seed(user.id, event_at=datetime(2027, 5, 9, 19, 30), title="Edge case")

    on_day = logged_in_client.get("/events/day?date=2027-05-10")
    day_before = logged_in_client.get("/events/day?date=2027-05-09")

    assert b"Edge case" in on_day.data
    assert b"Edge case" not in day_before.data


def test_day_agenda_invalid_or_missing_date_is_404(logged_in_client) -> None:
    assert logged_in_client.get("/events/day?date=not-a-date").status_code == 404
    assert logged_in_client.get("/events/day").status_code == 404


def test_month_grid_buckets_by_ist_date(session, make_user) -> None:
    user = make_user()
    _seed(user.id, event_at=datetime(2026, 8, 15, 4, 30), title="Mid-month")
    # 20:30 UTC Aug 31 is already 02:00 IST Sep 1 — bucket proves local-day math.
    _seed(user.id, event_at=datetime(2026, 8, 31, 20, 30), title="Month edge")

    grid = month_grid(user.id, 2026, 8)

    assert all(len(week) == 7 for week in grid["weeks"])
    assert grid["weeks"][0][0].weekday() == 0
    assert [event.title for event in grid["by_date"]["2026-08-15"]] == ["Mid-month"]
    assert [event.title for event in grid["by_date"]["2026-09-01"]] == ["Month edge"]
    assert "2026-08-31" not in grid["by_date"]


def test_activity_log_records_event_verbs(logged_in_client, session) -> None:
    _post_event(logged_in_client)
    event = db.session.query(Event).one()
    logged_in_client.post(f"/events/{event.id}/cancel")
    logged_in_client.post(f"/events/{event.id}/delete")

    verbs = {row.activity_type for row in db.session.query(ActivityLog).all()}

    assert {"event_created", "event_cancelled", "event_deleted"} <= verbs
