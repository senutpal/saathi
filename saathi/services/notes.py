"""Note query composition and the tag parse/sync engine."""

from __future__ import annotations

import re

from sqlalchemy import Select, or_, select

from ..extensions import db
from ..models import Note, Tag

_TAG_CLEAN_RE = re.compile(r"[^\w\- ]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_LIKE_ESCAPE_CHARS = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})


def like_escape(term: str) -> str:
    """Neutralize LIKE wildcards so user input matches literally (B08 pitfall #2)."""
    return term.translate(_LIKE_ESCAPE_CHARS)


def parse_tags(raw: str | None, *, limit: int = 8, max_len: int = 40) -> list[str]:
    """'"Work, WORK, deep work ,,' -> ['work', 'deep-work'] — deduped, order kept."""
    seen: set[str] = set()
    out: list[str] = []
    for part in (raw or "").split(","):
        cleaned = _TAG_CLEAN_RE.sub("", part.strip().lower())
        tag = _WS_RE.sub("-", cleaned).strip("-")[:max_len]
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
        if len(out) == limit:
            break
    return out


def sync_note_tags(note: Note, raw: str | None) -> None:
    """Replace the note's tag set with parsed names.

    One IN-query resolves existing rows; new Tags are batch-added; the full
    relationship replace drops removed associations in the same transaction.
    """
    names = parse_tags(raw)
    if names:
        existing = {
            t.name: t
            for t in db.session.scalars(
                select(Tag).where(Tag.user_id == note.user_id, Tag.name.in_(names))
            ).all()
        }
        fresh = [Tag(user_id=note.user_id, name=n) for n in names if n not in existing]
        db.session.add_all(fresh)
        note.tags = [*existing.values(), *fresh]
    else:
        note.tags = []


def filtered_notes(user_id: int, q: str = "", tag: str = "") -> Select[tuple[Note]]:
    """Active notes for one user, optionally LIKE-searched and/or tag-scoped.

    Ghost (soft-deleted) rows are excluded at the base — every list/search/
    count path composes from here so none can resurrect them (B08 pitfall #4).
    """
    stmt: Select[tuple[Note]] = select(Note).where(
        Note.user_id == user_id, Note.deleted_at.is_(None)
    )
    if q:
        pattern = f"%{like_escape(q)}%"
        stmt = stmt.where(
            or_(
                Note.title.ilike(pattern, escape="\\"),  # type: ignore[arg-type]
                Note.content.ilike(pattern, escape="\\"),  # type: ignore[arg-type]
            )
        )
    if tag:
        stmt = stmt.join(Note.tags).where(Tag.name == tag)
    return stmt
