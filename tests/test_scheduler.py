"""Ticker engine suite: idempotent firing, catch-up, recurrence, /tick auth."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.exc import OperationalError

from saathi import create_app
from saathi.extensions import db
from saathi.models import Event, Notification, User
from saathi.models.base import utcnow
from saathi.services import scheduler as sched


class FakeClock:
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
def make_event(session):
    def _make(
        user: User, *, event_at: datetime, title: str = "Demo", repeat_rule: str = "none", **kwargs
    ) -> Event:
        event = Event(
            user_id=user.id, title=title, event_at=event_at, repeat_rule=repeat_rule, **kwargs
        )
        db.session.add(event)
        db.session.commit()
        return event

    return _make


def _refresh(obj: object) -> object:
    db.session.expire_all()
    return db.session.get(type(obj), obj.id)  # type: ignore[attr-defined]


def _notifications() -> list[Notification]:
    return db.session.query(Notification).all()


def test_due_event_fires_exactly_once(clock, make_user, make_event) -> None:
    user = make_user()
    make_event(user, event_at=clock() - timedelta(minutes=5))

    first = sched.scan_and_fire(now_fn=clock)
    second = sched.scan_and_fire(now_fn=clock)

    assert (first, second) == (1, 0)
    assert len(_notifications()) == 1


def test_claim_stamps_status_and_fired_at(clock, make_user, make_event) -> None:
    user = make_user()
    event = make_event(user, event_at=clock() - timedelta(minutes=5))

    sched.scan_and_fire(now_fn=clock)

    refreshed = _refresh(event)
    assert refreshed.status == "fired"
    assert refreshed.fired_at == clock()


def test_catch_up_after_downtime_marks_fired_late(clock, make_user, make_event) -> None:
    user = make_user()
    event = make_event(user, event_at=clock() - timedelta(hours=2))

    fired = sched.scan_and_fire(now_fn=clock)

    assert fired == 1
    assert _refresh(event).status == "fired_late"
    assert len(_notifications()) == 1


def test_stale_one_shot_beyond_grace_is_missed_without_notification(
    clock, make_user, make_event
) -> None:
    user = make_user()
    event = make_event(user, event_at=clock() - timedelta(hours=25))

    fired = sched.scan_and_fire(now_fn=clock)

    assert fired == 1
    assert _refresh(event).status == "missed"
    assert _notifications() == []


def test_recurring_daily_rolls_successor_row(clock, make_user, make_event) -> None:
    user = make_user()
    due = clock() - timedelta(minutes=1)
    event = make_event(user, event_at=due, repeat_rule="daily")

    sched.scan_and_fire(now_fn=clock)

    rows = {row.id: row for row in db.session.query(Event).all()}
    assert _refresh(event).status == "fired"
    successor = next(row for row_id, row in rows.items() if row_id != event.id)
    assert successor.event_at == due + timedelta(days=1)
    assert successor.status == "scheduled"
    assert successor.fired_at is None
    assert successor.repeat_rule == "daily"


def test_recurring_past_grace_misses_but_still_rolls(clock, make_user, make_event) -> None:
    user = make_user()
    due = clock() - timedelta(hours=25)
    event = make_event(user, event_at=due, repeat_rule="monthly")

    sched.scan_and_fire(now_fn=clock)

    assert _refresh(event).status == "missed"
    assert _notifications() == []
    successors = [row for row in db.session.query(Event).all() if row.id != event.id]
    assert len(successors) == 1
    assert successors[0].event_at == sched.next_occurrence(due, "monthly")


@pytest.mark.parametrize(
    ("dt", "rule", "expected"),
    [
        (datetime(2027, 1, 31, 10, 0), "monthly", datetime(2027, 2, 28, 10, 0)),
        (datetime(2028, 1, 31, 10, 0), "monthly", datetime(2028, 2, 29, 10, 0)),
        (datetime(2026, 8, 24, 9, 0), "weekly", datetime(2026, 8, 31, 9, 0)),
        (datetime(2026, 12, 31, 23, 59), "daily", datetime(2027, 1, 1, 23, 59)),
    ],
)
def test_next_occurrence_calendar_math(dt: datetime, rule: str, expected: datetime) -> None:
    assert sched.next_occurrence(dt, rule) == expected


def test_next_occurrence_rejects_yearly() -> None:
    with pytest.raises(ValueError, match="yearly"):
        sched.next_occurrence(datetime(2027, 1, 31), "yearly")


def test_tick_without_configured_token_is_404(client) -> None:
    assert client.post("/tick").status_code == 404


def test_tick_with_wrong_token_is_404(app, client) -> None:
    app.config["TICK_TOKEN"] = "s3cret"

    response = client.post("/tick", headers={"X-Tick-Token": "nope"})

    assert response.status_code == 404


def test_tick_correct_token_runs_the_scan(app, client, make_user, make_event) -> None:
    app.config["TICK_TOKEN"] = "s3cret"
    # /tick scans with the real clock, so the seed must be relative to it —
    # a FakeClock date ages past MISFIRE_GRACE and silently becomes a miss.
    make_event(make_user(), event_at=utcnow() - timedelta(minutes=1))

    response = client.post("/tick", headers={"X-Tick-Token": "s3cret"})

    assert response.status_code == 200
    assert response.get_json() == {"fired": 1}
    assert len(_notifications()) == 1


def test_tick_is_exempt_from_csrf(app, client, make_user, make_event) -> None:
    app.config["TICK_TOKEN"] = "s3cret"
    app.config["WTF_CSRF_ENABLED"] = True
    make_event(make_user(), event_at=utcnow() - timedelta(minutes=1))

    response = client.post("/tick", headers={"X-Tick-Token": "s3cret"})

    assert response.status_code == 200
    assert response.get_json() == {"fired": 1}


def test_tick_rejects_get(client) -> None:
    assert client.get("/tick").status_code == 405


def test_scan_retries_once_after_transient_lock_error(
    app, clock, make_user, make_event, monkeypatch
) -> None:
    make_event(make_user(), event_at=clock())
    real_claim = sched._claim_one
    attempts = {"n": 0}

    def flaky_claim(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OperationalError("stmt", {}, Exception("database is locked"))
        return real_claim(*args, **kwargs)

    monkeypatch.setattr(sched, "_claim_one", flaky_claim)

    assert sched.scan_and_fire(now_fn=clock) == 1
    assert len(_notifications()) == 1


def test_concurrent_scans_cannot_double_notify(app, clock, make_user, make_event) -> None:
    make_event(make_user(), event_at=clock())
    barrier = threading.Barrier(2)

    def worker(_: int) -> int:
        with app.app_context():
            barrier.wait(timeout=5)
            return sched.scan_and_fire(now_fn=clock)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))

    db.session.expire_all()
    assert sum(results) == 1
    assert len(_notifications()) == 1
    statuses = [event.status for event in db.session.query(Event).all()]
    assert "scheduled" not in statuses


def test_start_ticker_refused_under_testing(app) -> None:
    assert sched.start_ticker(app) is False
    assert not [thread for thread in threading.enumerate() if thread.name == "events-ticker"]


def test_start_ticker_is_idempotent(app) -> None:
    app.config["TESTING"] = False
    app.config["SCHEDULER_ENABLED"] = True
    app.config["TICK_SECONDS"] = 3600
    try:
        assert sched.start_ticker(app) is True
        assert sched.start_ticker(app) is False
        assert len([t for t in threading.enumerate() if t.name == "events-ticker"]) == 1
    finally:
        sched.reset_for_tests()
        time.sleep(0.01)


def _gate_app(tmp_path, **extra):
    return create_app(
        test_config={
            "DATABASE_PATH": str(tmp_path / "gate.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            **extra,
        }
    )


def _dispose_engines(app) -> None:
    # pooled sqlite connections otherwise surface as ResourceWarnings on Windows
    with app.app_context():
        for engine in db.engines.values():
            engine.dispose()


def test_factory_starts_scheduler_for_plain_non_debug_run(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "saathi.services.scheduler.start_ticker", lambda app, **kw: calls.append(app)
    )
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

    app = _gate_app(tmp_path, DEBUG=False)
    _dispose_engines(app)

    assert len(calls) == 1


def test_factory_skips_reloader_parent_process(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "saathi.services.scheduler.start_ticker", lambda app, **kw: calls.append(app)
    )
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)

    app = _gate_app(tmp_path, DEBUG=True)
    _dispose_engines(app)

    assert calls == []


def test_factory_starts_in_reloader_child_process(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "saathi.services.scheduler.start_ticker", lambda app, **kw: calls.append(app)
    )
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")

    app = _gate_app(tmp_path, DEBUG=True)
    _dispose_engines(app)

    assert len(calls) == 1


def test_factory_booted_thread_claims_due_event_once(tmp_path) -> None:
    """Non-debug factory auto-starts the ticker; a due row is claimed exactly once."""
    app = create_app(
        test_config={
            "TESTING": False,
            "SCHEDULER_ENABLED": True,
            "TICK_SECONDS": 0.05,
            "DATABASE_PATH": str(tmp_path / "live.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )
    try:
        with app.app_context():
            db.create_all()
            user = User(username="ticky", email="ticky@example.com")
            user.set_password("long-enough-passphrase")
            db.session.add(user)
            db.session.flush()
            db.session.add(
                Event(user_id=user.id, title="Live", event_at=utcnow() - timedelta(seconds=30))
            )
            db.session.commit()

        assert sched.start_ticker(app) is False

        deadline = time.monotonic() + 5
        status = "scheduled"
        while time.monotonic() < deadline and status == "scheduled":
            with app.app_context():
                db.session.expire_all()
                status = db.session.query(Event).filter(Event.title == "Live").one().status
            time.sleep(0.05)

        assert status == "fired"
        with app.app_context():
            db.session.expire_all()
            assert len(db.session.query(Notification).all()) == 1
    finally:
        sched.reset_for_tests()
        _dispose_engines(app)


def test_zoneinfo_smoke_on_windows() -> None:
    aware = datetime(2026, 8, 24, 14, 30, tzinfo=UTC).astimezone(ZoneInfo("Asia/Kolkata"))

    assert aware.hour == 20
