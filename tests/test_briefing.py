"""Briefing dashboard: aggregates under a fixed clock, card degradation, scoping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import event

from saathi.extensions import db
from saathi.models import ActivityLog, Event, Note, Notification, Profile, User
from saathi.services import briefing
from saathi.utils import ist_to_utc_naive


def ist(hour: int, minute: int = 0, day: tuple[int, int, int] = (2026, 8, 25)) -> datetime:
    """IST wall time -> naive UTC coordinate; needs the session fixture context."""
    y, m, d = day
    return ist_to_utc_naive(datetime(y, m, d, hour, minute))


def clock_at(dt: datetime):
    return lambda: dt


def current_user_row() -> User:
    return db.session.query(User).filter_by(username="a").one()


def add_event(user: User, *, title: str, at_utc: datetime, status: str = "scheduled") -> Event:
    row = Event(user_id=user.id, title=title, event_at=at_utc, status=status)
    db.session.add(row)
    db.session.commit()
    return row


def test_today_and_overdue_are_disjoint_under_fixed_clock(session, make_user):
    user = make_user()
    add_event(user, title="fired-today", at_utc=ist(8), status="fired")
    add_event(user, title="later-today", at_utc=ist(18))
    add_event(user, title="yesterday-ignored", at_utc=ist(18, day=(2026, 8, 24)))

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    titles = [e.title for e in data["today_events"]]
    assert titles == ["fired-today", "later-today"]
    assert data["overdue_count"] == 1


def test_unread_count_excludes_read_notifications(session, make_user):
    user = make_user()
    db.session.add(Notification(user_id=user.id, title="unread-one"))
    db.session.add(
        Notification(user_id=user.id, title="read-one", read_at=datetime(2026, 8, 20, 1, 0))
    )
    db.session.commit()

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    assert data["unread_count"] == 1


def test_recent_notes_skip_soft_deleted_ghosts(session, make_user):
    user = make_user()
    db.session.add(Note(user_id=user.id, title="ghost", content="x", deleted_at=ist(12)))
    for i in range(4):
        db.session.add(Note(user_id=user.id, title=f"live-{i}", content="x"))
    db.session.commit()

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    names = [n.title for n in data["recent_notes"]]
    assert len(names) == 3
    assert "ghost" not in names
    assert "live-3" in names


def test_weather_card_hidden_without_city_config(logged_in_client):
    page = logged_in_client.get("/")

    assert b"Weather" not in page.data


def test_weather_card_renders_when_service_returns_payload(logged_in_client, app, monkeypatch):
    app.config["WEATHER_CITY"] = "Mumbai"
    monkeypatch.setattr(
        briefing,
        "get_weather",
        lambda city: {"city": city, "temp_c": 27, "wind_kmh": 13, "desc": "Mainly clear"},
    )

    page = logged_in_client.get("/")
    html = page.get_data(as_text=True)

    assert "Weather · Mumbai" in html
    assert "27°C" in html
    assert "Mainly clear" in html
    assert "Wind 13 km/h" in html


def test_weather_card_prefers_user_profile_city_over_fallback(logged_in_client, app, session, monkeypatch):
    app.config["WEATHER_CITY"] = "FallbackCity"
    user = User.query.filter_by(email="a@example.com").one()
    user.profile = Profile(full_name="Alice", city="Kalyani")
    session.commit()

    captured_city = []
    monkeypatch.setattr(
        briefing,
        "get_weather",
        lambda city: captured_city.append(city) or {"city": city, "temp_c": 30, "wind_kmh": 5, "desc": "Sunny"},
    )

    page = logged_in_client.get("/")
    assert "Weather · Kalyani" in page.get_data(as_text=True)
    assert captured_city == ["Kalyani"]


def test_weather_card_uses_ip_detection_when_profile_city_unset(logged_in_client, app, monkeypatch):
    app.config["WEATHER_CITY"] = "FallbackCity"
    monkeypatch.setattr(briefing, "get_client_ip", lambda: "103.1.2.3")
    monkeypatch.setattr(briefing, "get_city_from_ip", lambda ip: "Kolkata" if ip == "103.1.2.3" else None)

    captured_city = []
    monkeypatch.setattr(
        briefing,
        "get_weather",
        lambda city: captured_city.append(city) or {"city": city, "temp_c": 29, "wind_kmh": 8, "desc": "Rain"},
    )

    page = logged_in_client.get("/")
    assert "Weather · Kolkata" in page.get_data(as_text=True)
    assert captured_city == ["Kolkata"]


def test_is_public_ip_helper():
    from saathi.services.search import is_public_ip

    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("103.21.244.0") is True
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("192.168.1.1") is False
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip(None) is False
    assert is_public_ip("invalid-ip") is False


def test_on_this_day_picks_previous_years_entry(session, make_user):
    user = make_user()
    db.session.add(
        ActivityLog(
            user_id=user.id,
            activity_type="note_created",
            title="last-years-note",
            occurred_at=ist(10, day=(2025, 8, 25)),
        )
    )
    db.session.commit()

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    assert data["on_this_day"].title == "last-years-note"


def test_on_this_day_ignores_same_year_rows(session, make_user):
    user = make_user()
    db.session.add(
        ActivityLog(
            user_id=user.id,
            activity_type="note_created",
            title="this-years-note",
            occurred_at=ist(9),
        )
    )
    db.session.commit()

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    assert data["on_this_day"] is None


def test_greeting_tracks_local_time_of_day(session, make_user):
    user = make_user()

    assert briefing.build_briefing(user.id, now_fn=clock_at(ist(8)))["greeting"] == "Good morning"
    assert briefing.build_briefing(user.id, now_fn=clock_at(ist(22)))["greeting"] == "Good evening"


def test_seam_flags_true_once_pack_a_tables_landed(session, make_user):
    """Metadata probes flip permanently once models register."""
    user = make_user()

    data = briefing.build_briefing(user.id, now_fn=clock_at(ist(12)))

    assert data["has_habits"] is True
    assert data["has_contacts"] is True


def test_coming_soon_cards_hidden_while_tables_absent(logged_in_client):
    page = logged_in_client.get("/")

    assert b"Habits" in page.data
    assert b"Mood journal" in page.data


def test_no_cross_user_leakage_on_any_new_endpoint(make_user, login, client, session):
    alice = make_user(email="alice@example.com", username="alice")
    make_user(email="bob@example.com", username="bob")
    db.session.add(Event(user_id=alice.id, title="alices-event", event_at=ist(18)))
    db.session.add(Note(user_id=alice.id, title="alices-note", content="x"))
    db.session.add(Notification(user_id=alice.id, title="alices-notification"))
    db.session.add(
        ActivityLog(user_id=alice.id, activity_type="note_created", title="alices-history")
    )
    db.session.commit()

    login("bob@example.com", "correct horse")
    home = client.get("/").get_data(as_text=True)
    history = client.get("/history").get_data(as_text=True)
    export = client.get("/history/export.csv").get_data(as_text=True)

    for marker in ("alices-event", "alices-note", "alices-notification", "alices-history"):
        assert marker not in home
        assert marker not in history
        assert marker not in export


def test_dashboard_stays_within_query_budget(app, logged_in_client, session):
    user = current_user_row()
    add_event(user, title="today", at_utc=ist(18))
    db.session.add(Note(user_id=user.id, title="n1", content="x"))
    db.session.add(Notification(user_id=user.id, title="bell"))
    db.session.add(ActivityLog(user_id=user.id, activity_type="login", title="Signed in"))
    db.session.commit()

    statements: list[str] = []

    def count_hook(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", count_hook)
    try:
        response = logged_in_client.get("/")
    finally:
        event.remove(db.engine, "before_cursor_execute", count_hook)

    assert response.status_code == 200
    assert len(statements) <= 18, f"dashboard issued {len(statements)} queries"


# --- Life cards -------------------------------------------------------------


def test_birthday_card_renders_contact_inside_window(logged_in_client, session):
    from datetime import date, timedelta

    from saathi.models import Contact

    user = current_user_row()
    upcoming = date.today() + timedelta(days=3)
    db.session.add(
        Contact(
            user_id=user.id,
            name="Soon Sam",
            dob=date(upcoming.year - 30, upcoming.month, upcoming.day),
        )
    )
    db.session.commit()

    page = logged_in_client.get("/").get_data(as_text=True)

    assert "Birthdays" in page and "turns 30" in page


def test_birthday_card_absent_when_no_contacts_qualify(logged_in_client, session):
    from datetime import date, timedelta

    from saathi.models import Contact

    user = current_user_row()
    far_past = date.today() - timedelta(days=120)
    db.session.add(
        Contact(
            user_id=user.id,
            name="Ages Ago",
            dob=date(far_past.year - 20, far_past.month, max(far_past.day, 28)),
        )
    )
    db.session.commit()

    page = logged_in_client.get("/").get_data(as_text=True)

    assert "Birthdays" not in page


def test_habit_card_shows_streaks_or_empty_prompt(logged_in_client, session):
    from datetime import date, timedelta

    from saathi.models import Habit, HabitLog

    user = current_user_row()
    habit = Habit(user_id=user.id, name="Read", color="sky")
    db.session.add(habit)
    db.session.commit()
    for offset in range(3):
        db.session.add(HabitLog(habit_id=habit.id, log_date=date.today() - timedelta(days=offset)))
    db.session.commit()

    populated = logged_in_client.get("/").get_data(as_text=True)
    assert "3-day streak" in populated

    Habit.query.delete()
    db.session.commit()
    empty = logged_in_client.get("/").get_data(as_text=True)
    assert "No habits yet" in empty


def test_mood_card_degrades_to_prompt_without_entries(logged_in_client, session):

    empty = logged_in_client.get("/").get_data(as_text=True)
    assert "Log a daily score" in empty
