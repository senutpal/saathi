"""Notifications ladder suite: bell poll, inbox flows, best-effort email."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytest
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.engine import Engine

from saathi.extensions import db
from saathi.models import ActivityLog, Event, Notification, User
from saathi.models.base import utcnow
from saathi.services import mailer, scheduler


class FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 8, 25, 9, 0)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> datetime:
        self._now += timedelta(**kwargs)
        return self._now


def seed_event(clock: FakeClock, user_id: int, *, title: str = "Demo") -> int:
    event = Event(user_id=user_id, title=title, event_at=clock() - timedelta(minutes=1))
    db.session.add(event)
    db.session.flush()
    event_id = event.id
    db.session.commit()
    return event_id


def seed_notifications(user_id: int, count: int, *, read: bool = False) -> list[int]:
    rows = [Notification(user_id=user_id, title=f"Note {i}", body="body") for i in range(count)]
    if read:
        for row in rows:
            row.read_at = utcnow()
    db.session.add_all(rows)
    db.session.flush()
    ids = [row.id for row in rows]
    db.session.commit()
    return ids


def user_by_email(email: str = "a@example.com") -> User:
    db.session.expire_all()
    user = db.session.scalar(select(User).where(User.email == email))
    db.session.commit()
    return user


def login_as(client, email: str = "a@example.com") -> None:
    client.post("/auth/login", data={"email": email, "password": "correct horse"})


class _Recorder:
    def __init__(self, sink: FakeSmtplib, fail: bool) -> None:
        self._sink = sink
        self._fail = fail
        self.logins: list[tuple[str, str]] = []

    def __enter__(self) -> _Recorder:
        return self

    def __exit__(self, *args) -> bool:
        return False

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))

    def send_message(self, msg) -> None:
        if self._fail:
            raise RuntimeError("smtp down")
        self._sink.messages.append(msg)


class FakeSmtplib:
    """Drop-in shim for the one smtplib attribute mailer.py touches."""

    def __init__(self) -> None:
        self.messages: list = []
        self.fail = False

    def SMTP_SSL(self, host, port, timeout=None, context=None):  # noqa: N802 (stdlib name)
        return _Recorder(self, self.fail)


@pytest.fixture()
def fake_smtp(monkeypatch) -> FakeSmtplib:
    shim = FakeSmtplib()
    monkeypatch.setattr(mailer, "smtplib", shim)
    return shim


def test_fire_creates_notification_row(make_user) -> None:
    user = make_user()
    clock = FakeClock()
    event_id = seed_event(clock, user.id)

    fired = scheduler.scan_and_fire(now_fn=clock)

    db.session.expire_all()
    row = db.session.scalar(select(Notification))
    assert fired == 1
    assert row is not None
    assert (row.user_id, row.event_id, row.title) == (user.id, event_id, "Demo")
    assert row.read_at is None


def test_badge_shows_unread_on_poll_and_first_paint(logged_in_client, make_user) -> None:
    seed_notifications(user_by_email().id, 2)

    poll = logged_in_client.get("/notifications/count")
    home = logged_in_client.get("/")

    assert poll.status_code == 200
    assert ">2<" in poll.get_data(as_text=True)
    assert 'id="bell-count"' in home.get_data(as_text=True)


def test_mark_read_decrements_badge_and_restyles_inbox(logged_in_client) -> None:
    nid, other = seed_notifications(user_by_email().id, 2)

    marked = logged_in_client.post(f"/notifications/{nid}/read", follow_redirects=True)
    poll = logged_in_client.get("/notifications/count")

    body = marked.get_data(as_text=True)
    assert poll.status_code == 200
    assert ">1<" in poll.get_data(as_text=True)
    assert 'name="csrf_token"' in body or "name='csrf_token'" in body
    assert body.count(f"/notifications/{other}/read") == 1


def test_read_all_zeroes_badge_and_audits_once(logged_in_client) -> None:
    seed_notifications(user_by_email().id, 3)

    response = logged_in_client.post("/notifications/read-all", follow_redirects=True)
    poll = logged_in_client.get("/notifications/count")

    db.session.expire_all()
    audits = db.session.scalars(
        select(ActivityLog).where(ActivityLog.activity_type == "notifications_read_all")
    ).all()
    assert 'id="bell-count"' not in poll.get_data(as_text=True)
    assert len(audits) == 1
    assert "3" in audits[0].title
    assert "Mark read" not in response.get_data(as_text=True)


def test_mark_read_owner_checked_returns_404(client, make_user) -> None:
    alice = make_user(username="alice", email="alice@example.com")
    (nid,) = seed_notifications(alice.id, 1)
    make_user(username="bob", email="bob@example.com")
    login_as(client, "bob@example.com")

    hijack = client.post(f"/notifications/{nid}/read")

    db.session.expire_all()
    stolen = db.session.get(Notification, nid)
    assert hijack.status_code == 404
    assert stolen.read_at is None


def test_anonymous_poll_returns_286_without_leaking(client, make_user) -> None:
    alice = make_user(username="alice", email="alice@example.com")
    seed_notifications(alice.id, 1)

    response = client.get("/notifications/count")

    body = response.get_data(as_text=True)
    assert response.status_code == 286
    assert "Note 0" not in body


def test_email_disabled_gate_returns_no_thread_and_touches_nothing(app, fake_smtp) -> None:
    app.config["MAIL_ENABLED"] = False

    def explode(*args, **kwargs):
        raise AssertionError("SMTP must not be touched while MAIL_ENABLED is false")

    fake_smtp.SMTP_SSL = explode

    assert mailer.enqueue_email(app, [1, 2]) is None


def test_scan_hands_committed_ids_to_mailer_seam(make_user, monkeypatch) -> None:
    user = make_user()
    clock = FakeClock()
    seed_event(clock, user.id)
    handed: list[tuple[object, list[int]]] = []

    def record_seam(app_arg, ids):
        handed.append((app_arg, list(ids)))
        return None

    monkeypatch.setattr(scheduler, "enqueue_email", record_seam)

    scheduler.scan_and_fire(now_fn=clock)

    db.session.expire_all()
    row = db.session.scalar(select(Notification))
    assert len(handed) == 1
    assert handed[0][1] == [row.id]


def test_email_enabled_mocked_sends_to_owner(make_user, app, fake_smtp) -> None:
    user = make_user()
    app.config["MAIL_ENABLED"] = True
    (nid,) = seed_notifications(user.id, 1)

    thread = mailer.enqueue_email(app, [nid])
    assert thread is not None
    thread.join(timeout=10)

    assert len(fake_smtp.messages) == 1
    msg = fake_smtp.messages[0]
    assert msg["To"] == user.email
    assert "Note 0" in msg["Subject"]


def test_email_failure_keeps_row_and_logs_warning(caplog, make_user, app, fake_smtp) -> None:
    user = make_user()
    app.config["MAIL_ENABLED"] = True
    (nid,) = seed_notifications(user.id, 1)
    fake_smtp.fail = True

    with caplog.at_level(logging.WARNING, logger="saathi.email"):
        thread = mailer.enqueue_email(app, [nid])
        assert thread is not None
        thread.join(timeout=10)

    db.session.expire_all()
    row = db.session.get(Notification, nid)
    assert row is not None
    assert row.read_at is None
    assert any("SMTP send failed" in message for message in caplog.messages)


def test_xss_title_escaped_in_bell_and_inbox(logged_in_client, make_user) -> None:
    user = user_by_email()
    clock = FakeClock()
    seed_event(clock, user.id, title="<script>alert(1)</script>")

    scheduler.scan_and_fire(now_fn=clock)
    home = logged_in_client.get("/")
    inbox_page = logged_in_client.get("/notifications")

    home_body = home.get_data(as_text=True)
    inbox_body = inbox_page.get_data(as_text=True)
    assert "&lt;script&gt;" in home_body
    assert "<script>alert(1)" not in home_body
    assert "&lt;script&gt;" in inbox_body
    assert "<script>alert(1)" not in inbox_body


def test_inbox_pagination_pages_of_25(logged_in_client) -> None:
    seed_notifications(user_by_email().id, 26)

    first = logged_in_client.get("/notifications")
    second = logged_in_client.get("/notifications?page=2")
    overflow = logged_in_client.get("/notifications?page=999")

    first_body = first.get_data(as_text=True)
    assert first_body.count("Mark read") == 25
    assert second.get_data(as_text=True).count("Mark read") == 1
    assert "Page 1 of 2" in first_body
    assert "Page 2 of 2" in overflow.get_data(as_text=True)


def test_count_endpoint_is_a_single_select(logged_in_client) -> None:
    seed_notifications(user_by_email().id, 5)

    statements: list[str] = []

    def hook(_conn, _cursor, statement, *_args, **_kwargs) -> None:
        statements.append(statement)

    sqlalchemy.event.listen(Engine, "before_cursor_execute", hook)
    try:
        response = logged_in_client.get("/notifications/count")
    finally:
        sqlalchemy.event.remove(Engine, "before_cursor_execute", hook)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    from_notifications = [s for s in selects if "FROM notifications" in s]
    assert response.status_code == 200
    # The poll itself must add exactly ONE covering-index COUNT. Remaining
    # selects are the pre-existing per-request user load + its selectin
    # relationships (shared by every authed request, not poll-specific).
    assert len(from_notifications) == 1
    assert len(selects) <= 6
