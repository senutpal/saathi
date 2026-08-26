"""Weekly digest suite: Monday-only send, idempotency guard, preview, toggle."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import saathi.services.daily as daily
from saathi.extensions import db
from saathi.models import Contact, Event, User


class FakeClock:
    """Twin of test_scheduler's clock: Monday 2026-08-24 09:00 naive UTC."""

    def __init__(self) -> None:
        self._now = datetime(2026, 8, 24, 9, 0)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs: float) -> datetime:
        self._now += timedelta(**kwargs)
        return self._now


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def fake_send(monkeypatch):
    calls: list[str] = []

    def _send(to: str, subject: str, html: str, plain: str) -> bool:
        calls.append(to)
        return True

    monkeypatch.setattr(daily, "send_email", _send)
    return calls


@pytest.fixture(autouse=True)
def _reset_chore_memo():
    daily._last_chore_day = None
    yield
    daily._last_chore_day = None


def _enable(user_id: int) -> None:
    user = db.session.get(User, user_id)
    user.digest_enabled = True
    db.session.commit()


def test_digest_sends_once_per_monday_only(session, make_user, clock, fake_send) -> None:
    user = make_user()
    _enable(user.id)

    first = daily.maybe_daily_chores(now_fn=clock)
    second = daily.maybe_daily_chores(now_fn=clock)

    assert first == {"digests": 1}
    assert second == {}
    assert len(fake_send) == 1
    db.session.expire_all()
    assert db.session.get(User, user.id).digest_last_sent_at is not None

    clock.advance(days=3)
    wednesday = daily.maybe_daily_chores(now_fn=clock)
    assert wednesday == {"digests": 0}

    clock.advance(days=4)
    next_monday = daily.maybe_daily_chores(now_fn=clock)
    assert next_monday == {"digests": 1}
    assert len(fake_send) == 2


def test_failed_send_leaves_guard_unset_for_retry(session, make_user, clock, monkeypatch) -> None:
    user = make_user()
    _enable(user.id)

    stats = daily.maybe_daily_chores(now_fn=clock)

    assert stats == {"digests": 0}
    assert db.session.get(User, user.id).digest_last_sent_at is None

    # a process restart clears the memo; same Monday must retry the send
    daily._last_chore_day = None
    monkeypatch.setattr(daily, "send_email", lambda *a, **k: True)
    retried = daily.maybe_daily_chores(now_fn=clock)

    assert retried == {"digests": 1}


def test_disabled_user_is_never_emailed(session, make_user, clock, fake_send) -> None:
    make_user()
    clock.advance(days=7)
    clock.advance(days=7)

    stats = daily.maybe_daily_chores(now_fn=clock)

    assert stats == {"digests": 0}
    assert fake_send == []


def test_digest_context_carries_week_data(session, make_user, clock) -> None:
    from saathi.services.daily import digest_context

    user = make_user()
    db.session.add(
        Event(
            user_id=user.id,
            title="Dentist",
            event_at=clock() + timedelta(days=2),
        )
    )
    db.session.add(Contact(user_id=user.id, name="Meera", dob=datetime(2001, 8, 30).date()))
    db.session.commit()

    ctx = digest_context(user, now_fn=clock)

    assert [ev.title for ev in ctx["events"]] == ["Dentist"]
    assert ctx["overdue"] == 0
    assert ctx["birthdays"][0][0].name == "Meera"


def test_overdue_count_shows_in_preview(logged_in_client, session) -> None:
    user = db.session.query(User).first()
    db.session.add(Event(user_id=user.id, title="Ancient", event_at=datetime(2020, 1, 1, 9)))
    db.session.commit()

    body = logged_in_client.get("/digest/preview").get_data(as_text=True)

    assert "Your week ahead" in body
    assert "past due" in body


def test_digest_toggle_flips_flag(client, make_user, login, session) -> None:
    make_user(username="tog")
    login("a@example.com", "correct horse")

    client.post("/settings/digest-toggle", follow_redirects=True)
    assert db.session.query(User).filter_by(username="tog").one().digest_enabled is True

    client.post("/settings/digest-toggle", follow_redirects=True)
    assert db.session.query(User).filter_by(username="tog").one().digest_enabled is False


def test_anon_preview_redirects(client) -> None:
    assert client.get("/digest/preview").status_code == 302
