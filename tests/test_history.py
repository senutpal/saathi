"""History timeline: pagination, prefix filter persistence, CSV export, scoping."""

from __future__ import annotations

import re

from saathi.extensions import db
from saathi.models import ActivityLog, User


def seed_activity(user: User, activity_type: str, title: str) -> None:
    db.session.add(ActivityLog(user_id=user.id, activity_type=activity_type, title=title))
    db.session.commit()


def row_titles(html: str) -> list[str]:
    return re.findall(r'class="text-sm font-medium leading-snug">([^<]+)</p>', html)


def test_history_requires_login(client):
    response = client.get("/history")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_history_pagination_boundaries(logged_in_client, session):
    user = db.session.query(User).filter_by(username="a").one()
    for i in range(29):
        seed_activity(user, "note_created", f"row-{i:02d}")

    first = logged_in_client.get("/history")
    second = logged_in_client.get("/history?page=2")

    assert len(row_titles(first.get_data(as_text=True))) == 25
    assert len(row_titles(second.get_data(as_text=True))) == 5
    assert "Page 1 of 2" in first.get_data(as_text=True)
    assert "Page 2 of 2" in second.get_data(as_text=True)
    assert "row-28" in first.get_data(as_text=True)
    assert "row-00" in second.get_data(as_text=True)


def test_prefix_filter_shows_only_matching_family(logged_in_client, session):
    user = db.session.query(User).filter_by(username="a").one()
    seed_activity(user, "note_created", "a-note-row")
    seed_activity(user, "event_created", "an-event-row")
    seed_activity(user, "file_uploaded", "a-file-row")

    page = logged_in_client.get("/history?type=event_")

    titles = row_titles(page.get_data(as_text=True))
    assert titles == ["an-event-row"]
    assert 'value="event_" selected' in page.get_data(as_text=True)


def test_filter_persists_in_next_page_link(logged_in_client, session):
    user = db.session.query(User).filter_by(username="a").one()
    for i in range(27):
        seed_activity(user, "note_created", f"note-{i:02d}")

    page = logged_in_client.get("/history?type=note_")
    html = page.get_data(as_text=True)

    assert 'href="/history?page=2&amp;type=note_"' in html
    second = logged_in_client.get("/history?page=2&type=note_")
    assert len(row_titles(second.get_data(as_text=True))) == 2


def test_csv_export_streams_current_filter_with_header(logged_in_client, session):
    user = db.session.query(User).filter_by(username="a").one()
    seed_activity(user, "note_created", "csv-note")
    seed_activity(user, "event_cancelled", "csv-event")

    response = logged_in_client.get("/history/export.csv?type=note_")
    body = response.get_data(as_text=True)
    lines = body.strip().splitlines()

    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    assert lines[0] == "occurred_at,activity_type,title,details"
    assert len(lines) == 2
    assert ",note_created,csv-note," in lines[1]


def test_csv_export_quotes_formula_triggers(logged_in_client, session):
    user = db.session.query(User).filter_by(username="a").one()
    seed_activity(user, "note_created", "=SUM(A1:A2)")
    seed_activity(user, "note_updated", "+1 @cmd -flag")
    seed_activity(user, "note_deleted", "\tTabbed title")

    body = logged_in_client.get("/history/export.csv").get_data(as_text=True)

    assert "'=SUM(A1:A2)" in body
    assert "'+1 @cmd -flag" in body
    assert "'\tTabbed title" in body


def test_history_never_shows_another_users_rows(session, make_user, login, client):
    alice = make_user(email="alice@example.com", username="alice")
    make_user(email="bob@example.com", username="bob")
    seed_activity(alice, "note_created", "alices-private-row")

    login("bob@example.com", "correct horse")
    page = client.get("/history")
    export = client.get("/history/export.csv")

    assert "alices-private-row" not in page.get_data(as_text=True)
    assert "alices-private-row" not in export.get_data(as_text=True)


def test_unknown_filter_renders_empty_state(logged_in_client):
    page = logged_in_client.get("/history?type=zzz_")

    assert b"No activity for this filter" in page.data
