"""ICS subscribe feed suite: RFC 5545 output, token auth, rotation, headers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from icalendar import Calendar

from saathi.extensions import db
from saathi.models import Event, User
from saathi.services.ics import events_to_ical

TOKEN = "sample-token-value-1234567890abcdef"


def _make_event(user_id: int, *, when: datetime, title: str = "Demo", **kwargs) -> Event:
    event = Event(user_id=user_id, title=title, event_at=when, **kwargs)
    db.session.add(event)
    db.session.commit()
    return event


def _mint_token(user_id: int) -> None:
    user = db.session.get(User, user_id)
    user.ics_token = TOKEN
    db.session.commit()


def _fixed_now() -> datetime:
    return datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def test_round_trip_parses_uid_and_dtstart(session, make_user) -> None:
    user = make_user()
    _make_event(user.id, when=datetime(2026, 9, 1, 12, 30))

    body = events_to_ical(user, now_fn=_fixed_now)

    cal = Calendar.from_ical(body)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 1
    assert str(events[0]["uid"]) == f"event-{db.session.query(Event).first().id}@saathi"
    assert events[0].decoded("dtstart") == datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
    raw = body.decode()
    assert "DTSTART:20260901T123000Z" in raw
    assert "RRULE" not in raw


def test_no_rrule_despite_repeat_rule(session, make_user) -> None:
    user = make_user()
    _make_event(user.id, when=datetime(2026, 9, 1, 6, 0), title="Weekly", repeat_rule="weekly")

    assert b"RRULE" not in events_to_ical(user, now_fn=_fixed_now)


def test_rfc5545_escaping_survives_round_trip(session, make_user) -> None:
    user = make_user()
    tricky = 'Meet Ravi, CEO; bring "a,b"\nsecond line'
    _make_event(user.id, when=datetime(2026, 9, 2, 9, 0), title=tricky)

    cal = Calendar.from_ical(events_to_ical(user, now_fn=_fixed_now))
    event = next(iter(cal.walk("VEVENT")))

    assert str(event["summary"]) == tricky


def test_line_folding_keeps_every_line_leq_75_octets(session, make_user) -> None:
    user = make_user()
    _make_event(
        user.id,
        when=datetime(2026, 9, 3, 9, 0),
        title="Long",
        description="x" * 300,
    )

    lines = events_to_ical(user, now_fn=_fixed_now).split(b"\r\n")

    assert max(len(line) for line in lines) <= 75


def test_valarm_honors_event_lead_time(session, make_user) -> None:
    user = make_user()
    _make_event(user.id, when=datetime(2026, 9, 4, 9, 0), alert_lead_minutes=15)

    cal = Calendar.from_ical(events_to_ical(user, now_fn=_fixed_now))
    event = next(iter(cal.walk("VEVENT")))
    alarm = next(iter(event.walk("VALARM")))

    assert alarm.decoded("trigger") == timedelta(minutes=-15)


def test_cancelled_rows_are_excluded(session, make_user) -> None:
    user = make_user()
    _make_event(user.id, when=datetime(2026, 9, 5, 9, 0), status="cancelled")
    _make_event(user.id, when=datetime(2026, 9, 6, 9, 0), title="Alive")

    cal = Calendar.from_ical(events_to_ical(user, now_fn=_fixed_now))

    summaries = [str(ev["summary"]) for ev in cal.walk("VEVENT")]
    assert summaries == ["Alive"]


def test_empty_feed_is_valid_vcalendar_with_zero_events(session, make_user) -> None:
    user = make_user()

    cal = Calendar.from_ical(events_to_ical(user, now_fn=_fixed_now))

    assert str(cal["prodid"]) == "-//Saathi//Calendar 1.0//EN"
    assert str(cal["version"]) == "2.0"
    assert list(cal.walk("VEVENT")) == []


def test_bad_missing_and_revoked_tokens_are_uniform_404(client, session, make_user) -> None:
    other = make_user(email="p@example.com", username="other")
    _mint_token(other.id)

    responses = [
        client.get("/calendar.ics"),
        client.get("/calendar.ics?token=garbage"),
        client.get("/calendar.ics?token=revoked-old-token-value-abcdefghijklmnop"),
    ]

    assert all(resp.status_code == 404 for resp in responses)
    bodies = {resp.get_data() for resp in responses}
    assert len(bodies) == 1


def test_valid_token_serves_owner_feed_regardless_of_requester(
    client, make_user, login, session
) -> None:
    """Bearer semantics: the token IS the credential (B14 §2), so a valid
    token serves its owner's feed even from a stranger's browser session."""
    owner = make_user(email="o@example.com", username="owner")
    _make_event(owner.id, when=datetime(2026, 9, 1, 9, 0), title="Owner only")
    _mint_token(owner.id)
    stolen_url = f"/calendar.ics?token={owner.ics_token}"
    make_user(email="p@example.com", password="correct horse", username="peeper")
    login("p@example.com", "correct horse")

    response = client.get(stolen_url)

    assert response.status_code == 200
    assert b"Owner only" in response.get_data()


def test_good_token_returns_calendar_response(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    user.ics_token = TOKEN
    db.session.commit()

    response = logged_in_client.get(f"/calendar.ics?token={TOKEN}")

    assert response.status_code == 200
    assert response.content_type.startswith("text/calendar")
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "ETag" not in response.headers
    assert "Last-Modified" not in response.headers
    body = response.get_data()
    assert body.startswith(b"BEGIN:VCALENDAR")
    assert b"VERSION:2.0" in body and b"PRODID" in body


def test_regenerate_invalidates_old_token(client, make_user, login, session) -> None:
    make_user(username="rot")
    login("a@example.com", "correct horse")
    user = db.session.query(User).filter_by(username="rot").one()
    user.ics_token = TOKEN
    db.session.commit()
    assert client.get(f"/calendar.ics?token={TOKEN}").status_code == 200

    client.post("/settings/calendar-token/regenerate", follow_redirects=True)
    db.session.expire_all()
    refreshed = db.session.query(User).filter_by(username="rot").one().ics_token

    assert refreshed != TOKEN
    assert client.get(f"/calendar.ics?token={TOKEN}").status_code == 404
    assert client.get(f"/calendar.ics?token={refreshed}").status_code == 200


def test_settings_page_mints_token_lazily_once(logged_in_client, session) -> None:
    page_one = logged_in_client.get("/settings")
    user = db.session.query(User).one()
    minted = user.ics_token
    assert minted
    assert minted in page_one.get_data(as_text=True)

    logged_in_client.get("/settings")

    assert db.session.query(User).one().ics_token == minted


def test_anonymous_settings_redirects(client) -> None:
    assert client.get("/settings").status_code == 302
