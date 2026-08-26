"""Notes suite: markdown rendering, tags, search, pagination and ownership."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select, text

from saathi.extensions import db
from saathi.models import ActivityLog, Event, Note, User
from saathi.models.base import utcnow
from saathi.services.notes import filtered_notes, parse_tags, sync_note_tags


def _seed_note(user_id: int, *, title: str = "Seeded", content: str = "body", **kwargs) -> Note:
    note = Note(user_id=user_id, title=title, content=content, **kwargs)
    db.session.add(note)
    db.session.commit()
    return note


def _sole_user() -> User:
    return db.session.query(User).one()


def _user_by_email(email: str) -> User:
    return db.session.query(User).filter_by(email=email).one()


def _card_ids(html: str) -> list[str]:
    return sorted(set(re.findall(r'href="/notes/(\d+)"', html)))


def _plain(html: str) -> str:
    """Strip search-highlight markup so literal substring checks stay honest."""
    return html.replace("<mark>", "").replace("</mark>", "")


@pytest.fixture()
def other_client(client, make_user, login):
    make_user(email="b@example.com", password="other pass", username="b")
    client.post("/auth/logout")
    login("b@example.com", "other pass")
    yield client
    client.post("/auth/logout")


# --- S5 tag parsing ---------------------------------------------------------


def test_parse_tags_lowercases_dedupes_and_keeps_order():
    assert parse_tags("Work, WORK, deep work,,  ") == ["work", "deep-work"]


def test_parse_tags_caps_at_eight():
    raw = ", ".join(f"tag{i}" for i in range(12))

    assert parse_tags(raw) == [f"tag{i}" for i in range(8)]


def test_parse_tags_empty_input_yields_nothing():
    assert parse_tags("") == []
    assert parse_tags(None) == []


# --- S5 tag sync ------------------------------------------------------------


def test_sync_creates_missing_tags_and_replaces_set(session, make_user):
    user = make_user()
    note = _seed_note(user.id, title="Tagged")

    sync_note_tags(note, "Work, deep-work")
    db.session.commit()

    assert sorted(t.name for t in note.tags) == ["deep-work", "work"]

    sync_note_tags(note, "work")
    db.session.commit()

    refreshed = db.session.get(Note, note.id)
    assert [t.name for t in refreshed.tags] == ["work"]


# --- S1 list view -----------------------------------------------------------


def test_notes_require_login(client) -> None:
    response = client.get("/notes")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_list_renders_excerpt_without_markdown_noise(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Kickoff", content="# Decisions\n- **weekly** demo")
    sync_note_tags(note, "meetings")
    db.session.commit()

    page = logged_in_client.get("/notes").data.decode()

    assert "Kickoff" in page
    assert "weekly demo" in page
    assert "**" not in page
    assert 'href="/notes?tag=meetings"' in page


def test_list_pagination_is_20_per_page(logged_in_client, session):
    user = _sole_user()
    for i in range(25):
        db.session.add(Note(user_id=user.id, title=f"n{i:02d}", content="c"))
    db.session.commit()

    first = _card_ids(logged_in_client.get("/notes").data.decode())
    second = _card_ids(logged_in_client.get("/notes?page=2").data.decode())

    assert len(first) == 20
    assert len(second) == 5
    assert set(first) & set(second) == set()


def test_pager_preserves_search_term(logged_in_client, session):
    user = _sole_user()
    for i in range(25):
        title = f"hit {i}" if i < 21 else f"miss {i}"
        db.session.add(Note(user_id=user.id, title=title, content="c"))
    db.session.commit()

    page = logged_in_client.get("/notes?q=hit").data.decode()

    assert 'href="/notes?page=2&amp;q=hit"' in page


def test_tag_filter_returns_only_matching_notes(logged_in_client, session):
    user = _sole_user()
    work = _seed_note(user.id, title="work note", content="c")
    life = _seed_note(user.id, title="life note", content="c")
    sync_note_tags(work, "work")
    sync_note_tags(life, "home")
    db.session.commit()

    page = logged_in_client.get("/notes?tag=work").data.decode()

    assert "work note" in page
    assert "life note" not in page


# --- S6 search --------------------------------------------------------------


def test_search_matches_title_or_content_with_highlight(logged_in_client, session):
    user = _sole_user()
    _seed_note(user.id, title="Quarterly plan", content="nothing here")
    _seed_note(user.id, title="misc", content="the quarterly numbers look good")

    page = _plain(logged_in_client.get("/notes?q=quarterly").data.decode())

    assert "Quarterly plan" in page
    assert "quarterly numbers look good" in page
    assert "<mark>" in logged_in_client.get("/notes?q=quarterly").data.decode()


def test_search_wildcards_stay_literal(logged_in_client, session):
    user = _sole_user()
    _seed_note(user.id, title="boost 50% and snake_case", content="plain")
    _seed_note(user.id, title="ordinary note", content="other words")

    percent_page = _plain(logged_in_client.get("/notes?q=%").data.decode())
    underscore_page = _plain(logged_in_client.get("/notes?q=_").data.decode())
    backslash_status = logged_in_client.get("/notes?q=%5C").status_code

    assert "boost 50% and snake_case" in percent_page
    assert "ordinary note" not in percent_page
    assert "snake_case" in underscore_page
    assert "ordinary note" not in underscore_page
    assert backslash_status == 200


def test_search_composes_with_tag_filter(logged_in_client, session):
    user = _sole_user()
    hit = _seed_note(user.id, title="alpha roadmap", content="c")
    miss = _seed_note(user.id, title="alpha secret", content="c")
    sync_note_tags(hit, "work")
    sync_note_tags(miss, "home")
    db.session.commit()

    page = logged_in_client.get("/notes?q=alpha&tag=work").data.decode()

    assert "alpha roadmap" in page
    assert "alpha secret" not in page


def test_search_term_length_is_capped(logged_in_client):
    response = logged_in_client.get(f"/notes?q={'x' * 500}")

    assert response.status_code == 200


# --- S3 create / preview / edit ---------------------------------------------


def test_create_parses_tags_and_links_event(logged_in_client, session):
    user = _sole_user()
    event = Event(user_id=user.id, title="Sync", event_at=utcnow().replace(year=2030))
    db.session.add(event)
    db.session.commit()

    response = logged_in_client.post(
        "/notes/new",
        data={
            "title": "Minutes",
            "body": "**decisions** made",
            "tags": "Work, WORK, deep work",
            "event_id": str(event.id),
        },
    )

    assert response.status_code == 302
    note = db.session.query(Note).one()
    assert note.title == "Minutes"
    assert note.event_id == event.id
    assert sorted(t.name for t in note.tags) == ["deep-work", "work"]
    assert db.session.query(ActivityLog).filter_by(activity_type="note_created").count() == 1


def test_tampered_event_choice_is_rejected(logged_in_client):
    response = logged_in_client.post(
        "/notes/new",
        data={"title": "Sneaky", "body": "x", "event_id": "999999"},
    )
    page = response.data.decode()

    assert response.status_code == 200
    assert "Not a valid choice" in page
    assert db.session.query(Note).count() == 0


def test_preview_renders_sanitized_html_without_saving(logged_in_client, session):
    response = logged_in_client.post(
        "/notes/new",
        data={"title": "Draft", "body": "**bold** <script>alert(1)</script>", "preview": "Preview"},
    )
    page = response.data.decode()

    assert "<strong>bold</strong>" in page
    assert "&lt;script&gt;" in page
    assert not re.search(r"<script[^>]*>alert", page)
    assert db.session.query(Note).count() == 0
    assert "Draft" in page


def test_view_renders_markdown_body_through_md_filter(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Rich", content="## Heading\n\n- item one\n- item two")

    page = logged_in_client.get(f"/notes/{note.id}").data.decode()

    assert "<h2>Heading</h2>" in page
    assert "<li>item one</li>" in page


def test_view_xss_payload_is_inert(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(
        user.id,
        title="Evil",
        content="<script>alert(1)</script>\n\n[x](javascript:alert(1))",
    )

    response = logged_in_client.get(f"/notes/{note.id}")
    page = response.data.decode()

    assert response.status_code == 200
    assert "&lt;script&gt;" in page
    assert not re.search(r"<script[^>]*>alert", page)
    assert "[x](javascript:alert(1))" in page
    assert 'href="javascript:' not in page


def test_edit_updates_fields_and_replaces_tags(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Before", content="old body")
    sync_note_tags(note, "old-tag")
    db.session.commit()

    response = logged_in_client.post(
        f"/notes/{note.id}/edit",
        data={"title": "After", "body": "new body", "tags": "fresh-tag"},
    )

    assert response.status_code == 302
    refreshed = db.session.get(Note, note.id)
    assert refreshed.title == "After"
    assert refreshed.content == "new body"
    assert [t.name for t in refreshed.tags] == ["fresh-tag"]
    assert db.session.query(ActivityLog).filter_by(activity_type="note_updated").count() == 1


def test_edit_form_prefills_existing_values(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Prefill me", content="body text")
    sync_note_tags(note, "keep-me")
    db.session.commit()

    page = logged_in_client.get(f"/notes/{note.id}/edit").data.decode()

    assert 'value="Prefill me"' in page
    assert 'value="keep-me"' in page


# --- S7 trash lifecycle -----------------------------------------------------


def test_delete_hides_note_from_list_search_and_view(logged_in_client, session):
    user = _sole_user()
    ghost = _seed_note(user.id, title="Ghost note", content="boo")
    _seed_note(user.id, title="Live note", content="hello")
    sync_note_tags(ghost, "haunted")
    db.session.commit()

    response = logged_in_client.post(f"/notes/{ghost.id}/delete")

    assert response.status_code == 302
    assert logged_in_client.get(f"/notes/{ghost.id}").status_code == 404

    listing = logged_in_client.get("/notes").data.decode()
    assert "Live note" in listing
    assert "Ghost note" not in listing

    searched = logged_in_client.get("/notes?q=boo").data.decode()
    assert "Ghost note" not in searched

    tagged = logged_in_client.get("/notes?tag=haunted").data.decode()
    assert "Ghost note" not in tagged


def test_deleted_note_waits_in_trash_and_restore_revives_it(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Comeback", content="c")

    logged_in_client.post(f"/notes/{note.id}/delete")
    trash_page = logged_in_client.get("/notes/trash").data.decode()

    assert "Comeback" in trash_page
    assert f'action="/notes/{note.id}/restore"' in trash_page

    response = logged_in_client.post(f"/notes/{note.id}/restore")

    assert response.status_code == 302
    assert logged_in_client.get(f"/notes/{note.id}").status_code == 200
    assert "Comeback" in logged_in_client.get("/notes").data.decode()


def test_purge_hard_deletes_row_and_cascades_tags(logged_in_client, session):
    user = _sole_user()
    note = _seed_note(user.id, title="Doomed", content="c")
    sync_note_tags(note, "doomed-tag")
    db.session.commit()

    logged_in_client.post(f"/notes/{note.id}/delete")
    response = logged_in_client.post(f"/notes/{note.id}/purge")

    assert response.status_code == 302
    assert db.session.get(Note, note.id) is None
    junctions = db.session.execute(
        text("SELECT COUNT(*) FROM note_tags WHERE note_id = :nid"), {"nid": note.id}
    ).scalar_one()
    assert junctions == 0
    assert "Doomed" not in logged_in_client.get("/notes/trash").data.decode()


def test_trash_actions_on_active_note_return_404(logged_in_client, session):
    user = _sole_user()
    live = _seed_note(user.id, title="Alive", content="c")

    assert logged_in_client.post(f"/notes/{live.id}/restore").status_code == 404
    assert logged_in_client.post(f"/notes/{live.id}/purge").status_code == 404
    assert db.session.get(Note, live.id) is not None


def test_trash_actions_of_a_are_invisible_to_user_b(logged_in_client, other_client, session):
    owner = _user_by_email("a@example.com")
    note = _seed_note(owner.id, title="Not yours", content="c")

    assert other_client.post(f"/notes/{note.id}/delete").status_code == 404

    logged_in_client.post(f"/notes/{note.id}/delete")

    assert other_client.post(f"/notes/{note.id}/restore").status_code == 404
    assert other_client.post(f"/notes/{note.id}/purge").status_code == 404
    assert db.session.get(Note, note.id) is not None
    assert "Not yours" not in other_client.get("/notes/trash").data.decode()


# --- Activity hooks -----------------------------------------------------------


def test_lifecycle_writes_full_audit_trail_newest_first(logged_in_client, session):
    user = _sole_user()

    created = logged_in_client.post(
        "/notes/new", data={"title": "Audited", "body": "c", "tags": "life"}
    )
    note_id = int(created.headers["Location"].rsplit("/", 1)[-1])
    logged_in_client.post(f"/notes/{note_id}/edit", data={"title": "Audited!", "body": "c"})
    logged_in_client.post(f"/notes/{note_id}/delete")
    logged_in_client.post(f"/notes/{note_id}/restore")
    logged_in_client.post(f"/notes/{note_id}/delete")
    logged_in_client.post(f"/notes/{note_id}/purge")

    verbs = [
        row.activity_type
        for row in db.session.scalars(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user.id,
                ActivityLog.activity_type.like("note\\_%", escape="\\"),
            )
            .order_by(ActivityLog.id.desc())
        ).all()
    ]

    assert verbs == [
        "note_purged",
        "note_deleted",
        "note_restored",
        "note_deleted",
        "note_updated",
        "note_created",
    ]


# --- ownership ---------------------------------------------------------------


def test_notes_of_a_are_invisible_to_user_b(logged_in_client, other_client, session):
    owner = _user_by_email("a@example.com")
    note = _seed_note(owner.id, title="Private", content="secret")

    for path in (f"/notes/{note.id}", f"/notes/{note.id}/edit"):
        assert other_client.get(path).status_code == 404

    posted = other_client.post(f"/notes/{note.id}/edit", data={"title": "Hacked", "body": "x"})
    assert posted.status_code == 404
    assert db.session.get(Note, note.id).title == "Private"

    listing = other_client.get("/notes").data.decode()
    assert "Private" not in listing


def test_filtered_notes_service_scopes_to_one_user(session, make_user):
    a = make_user(email="a2@example.com", username="a2")
    b = make_user(email="b2@example.com", username="b2")
    _seed_note(a.id, title="mine", content="x")
    _seed_note(b.id, title="theirs", content="y")

    names = [n.title for n in db.session.scalars(filtered_notes(a.id)).all()]

    assert names == ["mine"]
