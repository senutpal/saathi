"""Notes routes: markdown notes CRUD, search and tag filtering."""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from ...extensions import db
from ...models import Note
from ...models.base import utcnow
from ...services.markdown import render_md
from ...services.notes import filtered_notes, sync_note_tags
from ...utils import get_own_or_404, log_action
from . import bp
from .forms import NoteForm

PER_PAGE = 20


def _active_or_404(note_id: int) -> Note:
    note = get_own_or_404(Note, note_id)
    if note.deleted_at is not None:
        abort(404)
    return note


def _form_values(form: NoteForm) -> dict:
    return {
        "title": form.title.data.strip(),
        "content": form.body.data or "",
        "event_id": form.event_id.data,
    }


@bp.get("")
def index() -> str:
    q = request.args.get("q", "").strip()[:100]
    tag = request.args.get("tag", "").strip()[:40]
    page = max(request.args.get("page", 1, type=int), 1)
    stmt = filtered_notes(current_user.id, q=q, tag=tag)
    pg = db.paginate(
        stmt.order_by(Note.pinned.desc(), Note.updated_at.desc()),
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template("notes/index.html", pg=pg, q=q, tag=tag)


@bp.route("/new", methods=["GET", "POST"])
def new() -> ResponseReturnValue:
    form = NoteForm()
    preview_html = None
    if form.validate_on_submit():
        if form.preview.data:
            preview_html = render_md(form.body.data or "")
        else:
            note = Note(user_id=current_user.id, **_form_values(form))
            db.session.add(note)
            sync_note_tags(note, form.tags.data)
            db.session.flush()
            note_id = note.id
            log_action(current_user.id, "note_created", form.title.data.strip()[:120])
            db.session.commit()
            flash("Note created.")
            return redirect(url_for("notes.view", note_id=note_id))
    return render_template("notes/form.html", form=form, preview_html=preview_html)


@bp.route("/<int:note_id>/edit", methods=["GET", "POST"])
def edit(note_id: int) -> ResponseReturnValue:
    note = _active_or_404(note_id)
    form = NoteForm()
    preview_html = None
    if form.validate_on_submit():
        if form.preview.data:
            preview_html = render_md(form.body.data or "")
        else:
            for key, value in _form_values(form).items():
                setattr(note, key, value)
            sync_note_tags(note, form.tags.data)
            log_action(current_user.id, "note_updated", note.title[:120])
            note_id = note.id
            db.session.commit()
            flash("Note updated.")
            return redirect(url_for("notes.view", note_id=note_id))
    form.title.data = note.title
    form.body.data = note.content
    form.tags.data = ", ".join(t.name for t in note.tags)
    form.event_id.data = note.event_id or 0
    return render_template("notes/form.html", form=form, note=note, preview_html=preview_html)


@bp.get("/<int:note_id>")
def view(note_id: int) -> str:
    note = _active_or_404(note_id)
    return render_template("notes/view.html", note=note)


@bp.post("/<int:note_id>/delete")
def delete(note_id: int) -> ResponseReturnValue:
    """Soft delete: ghosts keep living in Trash until restored or purged."""
    note = _active_or_404(note_id)
    note.deleted_at = utcnow()
    log_action(current_user.id, "note_deleted", note.title[:120])
    db.session.commit()
    flash("Note moved to trash.")
    return redirect(url_for("notes.index"))
