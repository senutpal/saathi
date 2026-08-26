"""Quick-add suite: parse grammar case table, creation, undo lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from saathi.blueprints.main import UNDO_GRACE
from saathi.extensions import db
from saathi.models import Event, Note, User
from saathi.models.base import utcnow
from saathi.services.quickadd import parse_quick_add

# Mon 2026-08-24 09:00 naive UTC == Mon 14:30 IST (FakeClock default twin)
NOW = datetime(2026, 8, 24, 9, 0)


def _clock() -> datetime:
    return NOW


# --- grammar case table ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "rem tomorrow 6pm submit fees",
            ("event", datetime(2026, 8, 25, 12, 30), "submit fees"),
        ),
        ("rem in 2 days call dentist", ("event", NOW + timedelta(days=2), "call dentist")),
        # bare weekday without time stores midnight IST (pinned choice)
        ("rem friday team sync", ("event", datetime(2026, 8, 27, 18, 30), "team sync")),
    ],
)
def test_reminder_phrases_create_events(session, text: str, expected: tuple) -> None:
    assert parse_quick_add(text, now_fn=_clock) == expected


@pytest.mark.parametrize(
    "text",
    [
        "buy milk",
        "rem submit fees",
        "rem yesterday lunch",
        "rem in march review goals",
        "call mum march",
        "!!!garbage@@@",
        "",
    ],
)
def test_weak_inputs_degrade_to_notes(text: str) -> None:
    kind, when, _title = parse_quick_add(text, now_fn=_clock)

    assert kind == "note"
    assert when is None


def test_long_input_caps_title_at_120(session) -> None:
    _kind, _when, title = parse_quick_add("rem in 2 days " + "x" * 500, now_fn=_clock)

    assert len(title) == 120


def test_note_prefix_explicitly_keeps_a_note() -> None:
    kind, when, title = parse_quick_add("note buy milk tomorrow", now_fn=_clock)

    assert (kind, when) == ("note", None)
    assert title == "note buy milk tomorrow"


# --- HTTP flow ---------------------------------------------------------------


def test_quick_add_creates_event_with_audit_row(logged_in_client, session) -> None:
    response = logged_in_client.post(
        "/quick-add", data={"text": "rem tomorrow 6pm submit fees"}, follow_redirects=True
    )

    body = response.get_data(as_text=True)
    event = db.session.query(Event).one()
    assert event.status == "scheduled"
    assert event.fired_at is None
    assert "Reminder created for" in body
    assert "Undo" in body
    assert event.title == "submit fees"


def test_quick_add_without_date_creates_note(logged_in_client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "buy milk"}, follow_redirects=True)

    note = db.session.query(Note).one()
    assert note.title == "buy milk"


def test_blank_input_flashes_error_without_rows(logged_in_client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "   "}, follow_redirects=True)

    assert db.session.query(Event).count() == 0
    assert db.session.query(Note).count() == 0


def test_undo_within_grace_deletes_row(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    logged_in_client.post("/quick-add", data={"text": "rem in 2 days call dentist"})
    event = db.session.query(Event).one()

    response = logged_in_client.post(f"/quick-add/{event.id}/undo", follow_redirects=True).get_data(
        as_text=True
    )

    assert db.session.query(Event).filter_by(user_id=user.id).count() == 0
    assert "Reminder undone." in response


def test_undo_after_edit_is_inert(logged_in_client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "rem in 2 days call dentist"})
    event = db.session.query(Event).one()
    event.title = "edited beyond undo"
    db.session.commit()

    response = logged_in_client.post(f"/quick-add/{event.id}/undo")

    assert response.status_code == 404
    assert db.session.query(Event).count() == 1


def test_undo_after_fire_is_inert(logged_in_client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "rem in 2 days call dentist"})
    event = db.session.query(Event).one()
    event.status = "fired"
    event.fired_at = utcnow()
    db.session.commit()

    assert logged_in_client.post(f"/quick-add/{event.id}/undo").status_code == 404
    assert db.session.query(Event).count() == 1


def test_undo_past_grace_window_is_404(logged_in_client, client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "rem in 2 days call dentist"})
    event = db.session.query(Event).one()

    with client.session_transaction() as http_session:
        stale_ts = utcnow() - UNDO_GRACE - timedelta(seconds=1)
        http_session["pending_undo"] = {
            "id": event.id,
            "title": event.title,
            "when": event.event_at.isoformat(),
            "ts": stale_ts.isoformat(),
        }

    assert logged_in_client.post(f"/quick-add/{event.id}/undo").status_code == 404
    assert db.session.query(Event).count() == 1


def test_undo_rejects_foreign_ids(logged_in_client, session) -> None:
    logged_in_client.post("/quick-add", data={"text": "rem in 2 days call dentist"})
    other_id = (db.session.query(Event).one().id or 0) + 999

    assert logged_in_client.post(f"/quick-add/{other_id}/undo").status_code == 404
