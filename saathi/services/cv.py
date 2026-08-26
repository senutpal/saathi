"""CV context builder: single source of truth for preview and both exports."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from flask import request

from ..models import EducationEntry, User, WorkEntry, utcnow

THEME_DIR = Path(__file__).resolve().parents[1] / "templates" / "cv" / "themes"
DEFAULT_THEME = "classic"
_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def available_themes() -> list[str]:
    """Theme names discovered by globbing the themes dir (one file = one theme)."""
    return sorted(p.name.removesuffix(".html.jinja") for p in THEME_DIR.glob("*.html.jinja"))


def resolve_theme() -> str:
    requested = request.args.get("theme", DEFAULT_THEME)
    return requested if requested in available_themes() else DEFAULT_THEME


def fmt_span(start: date | None, end: date | None) -> str:
    start_label = f"{start:%b %Y}" if start else "—"
    end_label = "Present" if end is None else f"{end:%b %Y}"
    return f"{start_label} – {end_label}"


def slugify(name: str) -> str:
    return (_SLUG_RE.sub("-", name.strip()).strip("-") or "cv").lower()


def _recency(entry: EducationEntry | WorkEntry) -> tuple[date, date]:
    return (entry.end_date or date.max, entry.start_date or date.min)


def build_cv_context(user: User) -> dict | None:
    """Data dict for CV themes, or None when there is nothing to render.

    Strict guard: needs a saved profile row AND at least one
    education/work entry; callers show the 409 warning page on None.
    """
    prof = user.profile
    if prof is None or not (user.education_entries or user.work_entries):
        return None

    edu = sorted(user.education_entries, key=_recency, reverse=True)[:10]
    work = sorted(user.work_entries, key=_recency, reverse=True)[:10]

    def _lines(text: str | None) -> list[str]:
        return [line for line in (text or "").splitlines() if line.strip()]

    return {
        "name": prof.full_name,
        "headline": prof.headline,
        "contact": " · ".join(filter(None, [prof.phone, (prof.address or "").split("\n")[0]])),
        "sex": prof.sex,
        "dob": prof.date_of_birth,
        "skills": [s.strip() for s in (prof.skills_csv or "").split(",") if s.strip()],
        "summary": prof.summary,
        "likes": _lines(prof.likes),
        "dislikes": _lines(prof.dislikes),
        "education": [
            {
                "title": ", ".join(filter(None, [e.qualification, e.field_of_study])),
                "org": e.institution,
                "span": fmt_span(e.start_date, e.end_date),
                "desc": e.description,
            }
            for e in edu
        ],
        "work": [
            {
                "role": w.role,
                "org": w.organization,
                "loc": w.location,
                "span": fmt_span(w.start_date, w.end_date),
                "desc": w.description,
            }
            for w in work
        ],
        "generated_at": utcnow(),
    }
