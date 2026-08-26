import sqlite3
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from saathi.extensions import db
from saathi.models import (
    ActivityLog,
    CapsuleMessage,
    EducationEntry,
    Event,
    Note,
    Notification,
    Profile,
    Tag,
    Upload,
    User,
    WorkEntry,
    utcnow,
)
from scripts.seed_demo import ALREADY_SEEDED, run_seed


def make_user(email: str = "a@example.com", username: str = "a") -> User:
    user = User(username=username, email=email)
    user.set_password("correct horse 8")
    return user


def add_fully_populated_user(session) -> User:
    user = make_user()
    user.profile = Profile(full_name="A Person")
    session.add(user)
    session.flush()

    event = Event(user=user, title="Stand-up", event_at=utcnow() + timedelta(days=1))
    note = Note(user=user, title="Minutes", content="# notes")
    note.tags.append(Tag(user=user, name="meetings"))
    session.add_all(
        [
            EducationEntry(user=user, institution="NIT", qualification="B.Tech"),
            WorkEntry(user=user, organization="Acme", role="Intern"),
            event,
            Notification(user=user, event=event, title=event.title),
            note,
            Upload(
                user=user,
                original_filename="photo.png",
                stored_filename=f"{uuid4().hex}.png",
                size_bytes=10,
            ),
            ActivityLog(user=user, activity_type="note_created", title="Created 'Minutes'"),
        ]
    )
    session.commit()
    return user


def count_of(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_foreign_keys_and_busy_timeout_pragmas_active(session) -> None:
    foreign_keys = session.execute(text("PRAGMA foreign_keys")).scalar_one()
    busy_timeout = session.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 5000


def test_wal_journal_mode_persists_on_file_database(app, session) -> None:
    raw = sqlite3.connect(app.config["DATABASE_PATH"])
    try:
        mode = raw.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        raw.close()

    assert mode == "wal"


def test_delete_user_cascades_every_owned_row(session) -> None:
    user = add_fully_populated_user(session)
    uid = user.id

    session.delete(user)
    session.commit()

    for model in (
        Profile,
        EducationEntry,
        WorkEntry,
        Event,
        Notification,
        Note,
        Tag,
        Upload,
        ActivityLog,
    ):
        assert count_of(session, model) == 0, model.__name__
    assert session.scalar(select(func.count()).select_from(db.metadata.tables["note_tags"])) == 0
    assert session.get(User, uid) is None


def test_deleting_event_nulls_note_and_notification_links(session) -> None:
    user = add_fully_populated_user(session)
    event = user.events[0]

    session.delete(event)
    session.commit()

    note = session.scalar(select(Note).where(Note.user_id == user.id))
    notification = session.scalar(select(Notification).where(Notification.user_id == user.id))

    assert note.event_id is None
    assert notification.event_id is None


def test_duplicate_email_rejected(session) -> None:
    session.add(make_user())
    session.commit()

    session.add(make_user(email="a@example.com", username="other"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_duplicate_username_rejected(session) -> None:
    session.add(make_user())
    session.commit()

    session.add(make_user(email="b@example.com", username="a"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_event_status_check_rejects_unknown_value(session) -> None:
    user = make_user()
    session.add(user)
    session.flush()

    session.add(Event(user=user, title="Bad", event_at=utcnow(), status="scheduled_lol"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_event_repeat_rule_check_rejects_unknown_value(session) -> None:
    user = make_user()
    session.add(user)
    session.flush()

    session.add(Event(user=user, title="Bad", event_at=utcnow(), repeat_rule="hourly"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_event_alert_lead_bounds_enforced(session) -> None:
    user = make_user()
    session.add(user)
    session.flush()

    session.add(Event(user=user, title="Bad", event_at=utcnow(), alert_lead_minutes=-1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_audit_stamps_populated_on_commit(session) -> None:
    add_fully_populated_user(session)

    user = session.scalar(select(User))
    upload = session.scalar(select(Upload))
    activity = session.scalar(select(ActivityLog))

    assert user.created_at is not None
    assert user.updated_at is not None
    assert upload.uploaded_at is not None
    assert activity.occurred_at is not None


def test_deferred_security_columns_default_off(session) -> None:
    session.add(make_user())
    session.commit()

    user = session.scalar(select(User))

    assert user.twofa_enabled is False
    assert user.digest_enabled is False
    assert user.ics_token is None
    assert user.totp_secret is None
    assert user.session_invalid_before is None
    assert user.digest_last_sent_at is None


def test_seed_is_idempotent(app) -> None:
    first = run_seed(app)
    second = run_seed(app)

    assert first.startswith("seeded demo@saathi.app")
    assert second == ALREADY_SEEDED


def test_seed_force_rebuilds_with_two_users(app) -> None:
    run_seed(app)
    run_seed(app, force=True)

    with app.app_context():
        users = db.session.scalars(select(User)).all()

    assert len(users) == 2
    assert {u.email for u in users} == {"demo@saathi.app", "alt@saathi.app"}


def test_seed_demo_credentials_and_due_reminder(app) -> None:
    run_seed(app, force=True)

    with app.app_context():
        demo = db.session.scalar(select(User).where(User.email == "demo@saathi.app"))

        assert demo.check_password("demo1234") is True
        assert demo.profile.full_name == "Demo Saathi"
        assert count_of(db.session, Event) == 4
        assert count_of(db.session, Note) == 2
        assert count_of(db.session, Tag) >= 2
        assert count_of(db.session, CapsuleMessage) == 1
        assert count_of(db.session, EducationEntry) == 1
        assert count_of(db.session, WorkEntry) == 1
        assert count_of(db.session, ActivityLog) >= 1

        standup = db.session.scalar(select(Event).where(Event.title == "Stand-up with mentor"))
        lead = standup.event_at - utcnow()

        assert timedelta(minutes=1) < lead <= timedelta(minutes=3)
