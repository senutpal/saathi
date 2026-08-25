"""Demo-data seeder for live demos and the viva run-sheet.

Never imported by app code. Run from the repo root:
    uv run python scripts/seed_demo.py [--force]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from io import BytesIO

from flask import Flask
from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from saathi import create_app
from saathi.extensions import db
from saathi.models import (
    ActivityLog,
    EducationEntry,
    Event,
    Note,
    Profile,
    Tag,
    User,
    WorkEntry,
    utcnow,
)
from saathi.services.uploads import save_upload

MARKER_EMAIL = "demo@saathi.app"
ALREADY_SEEDED = "already seeded; pass --force to rebuild"

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Size 4/Root 1 0 R>>\n%%EOF"
)


def _png_bytes() -> bytes:
    from PIL import Image

    im = Image.new("RGB", (320, 220))
    pixels = im.load()
    for x in range(320):
        for y in range(220):
            pixels[x, y] = (40 + x * 60 // 320, 60 + y * 80 // 220, 120)
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _demo_uploads(user: User) -> list[str]:
    """Route the demo files through the real validation ladder so the
    gallery, thumbs and audit rows all look production-born on stage."""
    items = [
        (_png_bytes(), "demo-gradient.png", "image/png"),
        (MINIMAL_PDF, "project-outline.pdf", "application/pdf"),
        (
            b"Saathi demo notes\n- upload ladder\n- gallery grid\n",
            "demo-notes.txt",
            "text/plain",
        ),
    ]
    made = []
    for data, name, content_type in items:
        storage = FileStorage(stream=BytesIO(data), filename=name, content_type=content_type)
        made.append(save_upload(storage, user).original_filename)
    return made


def run_seed(app: Flask, *, force: bool = False) -> str:
    """Populate the configured database; idempotent unless force rebuilds it."""
    with app.app_context():
        db.create_all()
        seeded = db.session.scalar(select(User).where(User.email == MARKER_EMAIL)) is not None
        if seeded and not force:
            return ALREADY_SEEDED
        if force:
            db.drop_all()
            db.create_all()

        demo = User(username="demo", email=MARKER_EMAIL)
        demo.set_password("demo1234")
        demo.profile = Profile(
            full_name="Demo Saathi",
            headline="Final-year CSE student",
            skills_csv="Python, Flask, SQL, Tailwind",
            summary="Building Saathi as my software-engineering semester project.",
            likes="Chai, long walks, open source",
            dislikes="Deadlines without reminders",
        )
        alt = User(username="alt", email="alt@saathi.app")
        alt.set_password("alt1234")

        soon = utcnow() + timedelta(minutes=2)
        later = utcnow() + timedelta(hours=3)
        tomorrow = utcnow().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        standup = Event(
            user=demo,
            title="Stand-up with mentor",
            event_at=soon,
            description="Show the ticker firing live.",
        )
        sync = Event(user=demo, title="Project sync", event_at=later)
        plants = Event(
            user=demo,
            title="Water the plants",
            event_at=tomorrow,
            repeat_rule="daily",
        )

        kickoff = Note(
            user=demo,
            title="Kickoff minutes",
            pinned=True,
            content="# Decisions\n- weekly demo\n- SQLite stays until deployment",
        )
        kickoff.tags.append(Tag(user=demo, name="meetings"))
        reading = Note(user=demo, title="Reading list", content="- Flask docs\n- nh3 README")
        reading.tags.append(Tag(user=demo, name="ideas"))

        db.session.add_all(
            [
                demo,
                alt,
                EducationEntry(
                    user=demo,
                    institution="National Institute of Technology",
                    qualification="B.Tech CSE",
                    start_date=date(2023, 8, 1),
                ),
                WorkEntry(
                    user=demo,
                    organization="Acme Labs",
                    role="Software Intern",
                    description="Built internal Flask dashboards.",
                ),
                standup,
                sync,
                plants,
                kickoff,
                reading,
                ActivityLog(
                    user=demo,
                    activity_type="note_created",
                    title="Created 'Kickoff minutes'",
                ),
                ActivityLog(
                    user=demo,
                    activity_type="event_created",
                    title="Created 'Stand-up with mentor'",
                ),
            ]
        )
        db.session.commit()
        made = _demo_uploads(demo)
    files = ", ".join(made)
    return f"seeded {MARKER_EMAIL} / demo1234 (+1 alt user); files: {files}; reminder due in ~2 min"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="drop and reseed even if seeded")
    args = parser.parse_args()
    print(run_seed(create_app(), force=args.force))


if __name__ == "__main__":
    main()
