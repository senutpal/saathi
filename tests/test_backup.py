"""Backup feature: scoped export (leak gate), atomic import, CSV cells."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from saathi.extensions import db
from saathi.models import ActivityLog, Contact, Event, Mood, Note, User
from saathi.services.backup import ImportRejected, apply_import, export_payload

pytestmark = pytest.mark.filterwarnings("ignore::ResourceWarning")


def _seed_rich(alice_id: int) -> None:
    event = Event(user_id=alice_id, title="standup", event_at=datetime(2026, 8, 27, 10, 0))
    db.session.add(event)
    db.session.flush()
    db.session.add(Contact(user_id=alice_id, name="Ada", dob=date(2000, 2, 29)))
    note = Note(user_id=alice_id, title="linked-note", content="body", event_id=event.id)
    db.session.add(note)
    db.session.flush()
    db.session.add(
        ActivityLog(user_id=alice_id, activity_type="note_created", title="x", event_id=event.id)
    )
    db.session.commit()


def test_export_contains_zero_rows_from_any_other_user(session, make_user):
    """CI GATE (B17 T5): one unscoped SELECT in export = catastrophic breach."""
    alice = make_user(username="alice", email="alice@example.com")
    bob = make_user(username="bob", email="bob@example.com")
    _seed_rich(alice.id)
    db.session.add(Contact(user_id=bob.id, name="BOBS-SECRET"))
    db.session.commit()

    payload = export_payload(bob)

    for table, rows in payload["tables"].items():
        assert rows == [] or table == "contacts", f"{table} leaked rows"
    assert "BOBS-SECRET" in json.dumps(payload["tables"]["contacts"])
    assert "Ada" not in json.dumps(payload)


def test_export_streams_unicode_attachment(session, logged_in_client):
    user = db.session.query(User).first()
    db.session.add(Contact(user_id=user.id, name="Renée ✉"))
    db.session.commit()

    response = logged_in_client.get("/export.json")
    raw = response.get_data(as_text=True)

    assert "attachment" in response.headers["Content-Disposition"]
    assert "saathi-backup-" in response.headers["Content-Disposition"]
    assert "Renée ✉" in raw  # ensure_ascii=False keeps unicode literal


def test_share_state_is_never_exported_nor_trusted_on_import(session, make_user):
    """Live tokens must not travel: UNIQUE collision + cross-account squatting."""
    from saathi.models import Profile
    from saathi.services.backup import SCHEMA_VERSION

    alice = make_user(username="alice", email="alice@example.com")
    profile = Profile(user_id=alice.id, full_name=alice.username)
    profile.public_token = "live-token-abc"
    profile.share_enabled = True
    db.session.add(profile)
    db.session.commit()

    payload = export_payload(db.session.get(User, alice.id))
    exported = json.dumps(payload)
    assert "live-token-abc" not in exported
    assert "share_enabled" not in exported

    bob = make_user(username="bob", email="bob@example.com")
    hostile = {
        "schema": SCHEMA_VERSION,
        "tables": {
            "profiles": [{"full_name": "X", "public_token": "squat", "share_enabled": True}]
        },
    }

    apply_import(db.session.get(User, bob.id), hostile)

    fresh = db.session.query(Profile).filter_by(full_name="X").one()
    assert fresh.public_token is None and fresh.share_enabled is False


def test_import_remaps_child_fks_and_forces_owner(session, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    bob = make_user(username="bob", email="bob@example.com")
    _seed_rich(alice.id)
    payload = export_payload(db.session.get(User, alice.id))

    counts = apply_import(db.session.get(User, bob.id), payload)

    assert counts["notes"] == counts["events"] == counts["activity_log"] == 1
    imported_note = db.session.query(Note).filter_by(user_id=bob.id).one()
    assert imported_note.event_id is not None
    log_row = (
        db.session.query(ActivityLog)
        .filter_by(user_id=bob.id)
        .order_by(ActivityLog.id.desc())
        .first()
    )
    assert log_row.event_id is not None
    assert db.session.query(Contact).filter_by(user_id=bob.id).count() == 1


def test_tampered_user_ids_are_overwritten_with_importer(session, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    bob = make_user(username="bob", email="bob@example.com")
    _seed_rich(alice.id)
    payload = export_payload(db.session.get(User, alice.id))
    payload["tables"]["contacts"][0]["user_id"] = bob.id
    payload["tables"]["contacts"][0]["user_id"] = alice.id + bob.id

    apply_import(db.session.get(User, bob.id), payload)

    rows = db.session.query(Contact).filter_by(user_id=bob.id).all()
    assert len(rows) == 1


def test_bad_row_rolls_back_every_table_and_names_offender(session, make_user):
    alice = make_user(username="alice", email="alice@example.com")
    bob = make_user(username="bob", email="bob@example.com")
    _seed_rich(alice.id)
    good = export_payload(db.session.get(User, alice.id))
    bad = json.loads(json.dumps(good))
    bad["tables"]["moods"] = [{"mood_date": "2026-08-26", "score": 9}]

    try:
        apply_import(db.session.get(User, bob.id), bad)
        raised = False
    except ImportRejected as exc:
        raised = True
        assert "moods" in str(exc)

    assert raised
    # atomicity proof: nothing from the failed pass survived
    assert db.session.query(Contact).filter_by(user_id=bob.id).count() == 0
    assert db.session.query(Note).filter_by(user_id=bob.id).count() == 0
    assert db.session.query(Mood).filter_by(user_id=bob.id).count() == 0

    counts = apply_import(db.session.get(User, bob.id), good)  # clean copy still works
    assert counts["contacts"] == 1


def test_wrong_schema_version_is_refused(session, make_user):
    alice = make_user()

    try:
        apply_import(alice, {"schema": "saathi-v9", "tables": {}})
    except ImportRejected as exc:
        assert "saathi-v1" in str(exc)
    else:
        raise AssertionError("wrong schema accepted")


def test_unknown_table_key_is_refused(session, make_user):
    alice = make_user()

    try:
        apply_import(alice, {"schema": "saathi-v1", "tables": {"users": [], "shady": []}})
    except ImportRejected as exc:
        assert "users" in str(exc) and "shady" in str(exc)
    else:
        raise AssertionError("unknown tables accepted")


def test_dangling_fk_reference_is_refused(session, make_user):
    alice = make_user()
    payload = {
        "schema": "saathi-v1",
        "tables": {
            "events": [],
            "notes": [
                {
                    "id": 5,
                    "title": "orphan",
                    "content": "x",
                    "pinned": False,
                    "archived": False,
                    "deleted_at": None,
                    "event_id": 999,
                    "created_at": "2026-08-26T10:00:00",
                    "updated_at": "2026-08-26T10:00:00",
                }
            ],
        },
    }

    try:
        apply_import(alice, payload)
    except ImportRejected as exc:
        assert "event_id" in str(exc)
    else:
        raise AssertionError("dangling FK accepted")


def test_expenses_csv_uses_divmod_cells_and_bom(session, make_user, client, login):
    from saathi.models import Expense

    alice = make_user(email="alice@example.com", username="alice")
    db.session.add(
        Expense(
            user_id=alice.id,
            amount_cents=999,
            spent_on=date(2026, 8, 26),
            category="books",
            note="=cmd|' /c calc!A0",
        )
    )
    db.session.commit()

    login("alice@example.com", "correct horse")
    response = client.get("/export/expenses.csv")

    body = response.get_data(as_text=True)
    assert response.headers["Content-Type"].startswith("text/csv")
    assert body.startswith("\ufeffamount,currency,category")
    assert "\n9.99,INR,books,2026-08-26,'=cmd|' /c calc!A0" in body or "'=cmd" in body


def test_backup_require_login_redirects_anonymous(client):
    response = client.get("/backup")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_backup_index_renders(logged_in_client):
    response = logged_in_client.get("/backup")
    assert response.status_code == 200
    assert b"backup" in response.data.lower()


def test_import_json_no_file_redirects(logged_in_client):
    response = logged_in_client.post("/import.json", data={})
    assert response.status_code == 302


def test_import_json_too_large_aborts_413(logged_in_client):
    import io
    import warnings

    warnings.simplefilter("ignore", ResourceWarning)
    big_file = (io.BytesIO(b"[" * (10 * 1024 * 1024 + 10)), "big.json")
    response = logged_in_client.post("/import.json", data={"file": big_file})
    assert response.status_code == 413


def test_import_json_invalid_json_redirects(logged_in_client):
    import io

    bad_file = (io.BytesIO(b"not json"), "bad.json")
    response = logged_in_client.post("/import.json", data={"file": bad_file})
    assert response.status_code == 302


def test_import_json_rejected_import_redirects(logged_in_client):
    import io
    import json

    payload = {"tables": {}}
    bad_file = (io.BytesIO(json.dumps(payload).encode()), "bad.json")
    response = logged_in_client.post("/import.json", data={"file": bad_file})
    assert response.status_code == 302


def test_import_json_success_redirects(logged_in_client):
    import io
    import json

    from saathi.services.backup import SCHEMA_VERSION

    payload = {"schema": SCHEMA_VERSION, "tables": {"notes": []}}
    good_file = (io.BytesIO(json.dumps(payload).encode()), "good.json")
    response = logged_in_client.post("/import.json", data={"file": good_file})
    assert response.status_code == 302
