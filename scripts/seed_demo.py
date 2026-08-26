"""Demo-data seeder for live demos and the viva run-sheet.

Never imported by app code. Run from the repo root:
    uv run python scripts/seed_demo.py [--force]
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import Flask
from sqlalchemy import select
from werkzeug.datastructures import FileStorage

from saathi import create_app
from saathi.extensions import db
from saathi.models import (
    ActivityLog,
    CapsuleMessage,
    Contact,
    EducationEntry,
    Event,
    Expense,
    Habit,
    HabitLog,
    Mood,
    Note,
    Profile,
    Tag,
    User,
    WorkEntry,
    utcnow,
)
from saathi.services.uploads import save_upload
from saathi.utils import ist_to_utc_naive

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

        def audit(activity_type: str, title: str, *, days_ago: int = 0) -> ActivityLog:
            row = ActivityLog(
                user=demo, activity_type=activity_type, title=title, occurred_at=utcnow()
            )
            if days_ago:
                row.occurred_at -= timedelta(days=days_ago)
            return row

        last_year = utcnow() - timedelta(days=365)
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
                audit("note_created", "Created 'Kickoff minutes'"),
                audit("event_created", "Created 'Stand-up with mentor'"),
                audit("file_uploaded", "demo-gradient.png", days_ago=1),
                audit("web_search_web", "flask tutorial", days_ago=2),
                audit("login", "Signed in", days_ago=3),
                ActivityLog(
                    user=demo,
                    activity_type="note_created",
                    title="On-this-day: started Saathi",
                    occurred_at=last_year,
                ),
            ]
        )
        db.session.commit()
        made = _demo_uploads(demo)
        _demo_life_rows(demo)
        _demo_pack_b_rows(demo)
    files = ", ".join(made)
    return f"seeded {MARKER_EMAIL} / demo1234 (+1 alt user); files: {files}; reminder due in ~2 min"


def _demo_life_rows(user: User) -> None:
    """Pack-A demo data: one birthday due, streaks, a mood week, some spend."""
    from decimal import Decimal

    from saathi.utils import ist_today

    today = ist_today()
    birthday_soon = today + timedelta(days=3)

    def dob_for(year: int) -> date | None:
        # Feb-29 target year may be common -> celebrate Feb-28 like the engine
        try:
            return date(year, birthday_soon.month, birthday_soon.day)
        except ValueError:
            return date(year, 2, 28)

    rows = [
        Contact(
            user_id=user.id,
            name="Meera (b-day in 3 days)",
            phone="+91 98765 43210",
            email="meera@example.com",
            dob=dob_for(2002),
            notes="Loves filter coffee.",
        ),
        Contact(
            user_id=user.id,
            name="Ravi",
            phone="+91 90000 11122",
            dob=date(2000, 2, 29),  # exercises the Feb-29 fallback on the card
        ),
        Habit(user_id=user.id, name="Read 20 pages", color="sky"),
        Habit(user_id=user.id, name="Morning walk", color="emerald"),
    ]
    db.session.add_all(rows)
    db.session.flush()
    read_habit, walk_habit = rows[2], rows[3]
    for offset in range(9):  # current streak of 9 -> flame on the dashboard
        db.session.add(HabitLog(habit_id=read_habit.id, log_date=today - timedelta(days=offset)))
    for offset in range(4):
        db.session.add(HabitLog(habit_id=walk_habit.id, log_date=today - timedelta(days=offset)))

    scores = (3, 4, 4, 2, 3, 5, 4)
    for idx, score in enumerate(scores):
        db.session.add(
            Mood(
                user_id=user.id,
                mood_date=today - timedelta(days=len(scores) - 1 - idx),
                score=score,
                note="demo day" if score == 5 else None,
            )
        )

    spends = [
        ("249.50", "books", 0, "Flask in Action"),
        ("60.00", "food", 0, "Canteen"),
        ("750.00", "bills", 2, "Broadband"),
        ("120.00", "travel", 3, "Metro card"),
        ("499.00", "fun", 5, "Concert"),
        ("89.99", "food", 6, ""),
    ]
    for amount, category, days_ago, note in spends:
        cents = int((Decimal(amount) * 100).to_integral_exact())
        db.session.add(
            Expense(
                user_id=user.id,
                amount_cents=cents,
                category=category,
                spent_on=today - timedelta(days=days_ago),
                note=note or None,
            )
        )
    db.session.commit()


def _demo_pack_b_rows(user: User) -> None:
    """Pack-B demo data: tomorrow-09:00 IST event + capsule for digest/ICS."""
    from datetime import time as dtime

    from saathi.utils import ist_today

    opens_at = ist_to_utc_naive(datetime.combine(ist_today() + timedelta(days=1), dtime(9, 0)))
    db.session.add_all(
        [
            Event(
                user_id=user.id,
                title="Demo day dry-run",
                event_at=opens_at,
                description="Final rehearsal — projector at 9.",
            ),
            CapsuleMessage(
                user_id=user.id,
                title="Read me tomorrow",
                body="If you are reading this, the capsule worked.\n\n"
                "Remember why you started building Saathi: small tools, "
                "honestly shipped, beat big plans. Keep going.\n\n"
                "— past you",
                open_at=opens_at,
            ),
        ]
    )
    db.session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="drop and reseed even if seeded")
    args = parser.parse_args()
    print(run_seed(create_app(), force=args.force))


if __name__ == "__main__":
    main()
