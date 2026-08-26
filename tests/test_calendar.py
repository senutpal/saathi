"""Month-calendar suite: grid shape, IST bucketing, overlays, overflow, auth."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from saathi.extensions import db
from saathi.models import Contact, Event, Habit, HabitLog, User
from saathi.services.agenda import build_calendar


def _make_event(user_id: int, *, when_utc_naive: datetime, title: str = "Demo") -> Event:
    event = Event(user_id=user_id, title=title, event_at=when_utc_naive)
    db.session.add(event)
    db.session.commit()
    return event


def _login_as(client, login, email: str) -> None:
    client.post("/auth/logout")
    login(email, "correct horse")


def test_leap_february_has_29_cells_and_five_weeks(session, make_user) -> None:
    user = make_user()

    grid = build_calendar(user.id, 2028, 2, today=date(2028, 2, 10))

    in_month = [cell for week in grid["weeks"] for cell in week if cell["in_month"]]
    assert len(in_month) == 29
    assert len(grid["weeks"]) == 5
    out_month = {cell["iso"] for week in grid["weeks"] for cell in week if not cell["in_month"]}
    assert {"2028-03-01", "2028-03-04"} <= out_month


def test_event_at_2030z_buckets_into_next_ist_day(session, make_user) -> None:
    user = make_user()
    _make_event(user.id, when_utc_naive=datetime(2026, 8, 5, 20, 30), title="Late ping")

    grid = build_calendar(user.id, 2026, 8, today=date(2026, 8, 5))

    labels = [chip["label"] for chip in grid["by_date"].get("2026-08-06", [])]
    assert labels == ["02:00 Late ping"]


def test_today_highlight_marks_exactly_one_cell(logged_in_client, session) -> None:
    body = logged_in_client.get("/calendar").get_data(as_text=True)

    assert body.count("data-today=") == 1


def test_overflow_renders_three_chips_plus_more_link(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    base = datetime(2026, 8, 14, 4, 0)
    for idx in range(6):
        _make_event(user.id, when_utc_naive=base + timedelta(hours=idx), title=f"Item {idx}")

    body = logged_in_client.get("/calendar?month=2026-08").get_data(as_text=True)

    assert body.count(">+3 more</a>") == 1
    assert "Item 2" in body
    assert "Item 3" not in body


def test_garbage_month_is_404(logged_in_client, session) -> None:
    assert logged_in_client.get("/calendar?month=oops").status_code == 404


def test_cross_user_events_stay_hidden(client, make_user, login, session) -> None:
    owner = make_user(email="o@example.com", username="owner")
    _make_event(owner.id, when_utc_naive=datetime(2026, 8, 14, 9, 0), title="Owner secret")
    make_user(email="b@example.com", password="correct horse", username="bee")

    _login_as(client, login, "b@example.com")

    body = client.get("/calendar?month=2026-08").get_data(as_text=True)
    assert "Owner secret" not in body


def test_birthday_chip_overlays_contact_dob(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    db.session.add(Contact(user_id=user.id, name="Meera", dob=date(2001, 8, 20)))
    db.session.commit()

    body = logged_in_client.get("/calendar?month=2026-08").get_data(as_text=True)

    assert ">Meera<" in body


def test_habit_chip_overlays_logged_day(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    habit = Habit(user_id=user.id, name="Read", color="sky")
    db.session.add(habit)
    db.session.flush()
    today = date.today()
    db.session.add(HabitLog(habit_id=habit.id, log_date=today))
    db.session.commit()

    body = logged_in_client.get(f"/calendar?month={today:%Y-%m}").get_data(as_text=True)

    assert ">Read<" in body


def test_anonymous_user_redirects_to_login(client) -> None:
    response = client.get("/calendar")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
