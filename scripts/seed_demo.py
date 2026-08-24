"""Demo-data seeder for live demos and the viva run-sheet.

Never imported by app code. Run from the repo root:
    uv run python scripts/seed_demo.py [--force]
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from flask import Flask

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

MARKER_EMAIL = "demo@saathi.app"
ALREADY_SEEDED = "already seeded; pass --force to rebuild"


def run_seed(app: Flask, *, force: bool = False) -> str:
    """Populate the configured database; idempotent unless force rebuilds it."""
    with app.app_context():
        db.create_all()
        seeded = db.session.query(User).filter_by(email=MARKER_EMAIL).first() is not None
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
    return f"seeded {MARKER_EMAIL} / demo1234 (+1 alt user); reminder due in ~2 min"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="drop and reseed even if seeded")
    args = parser.parse_args()
    print(run_seed(create_app(), force=args.force))


if __name__ == "__main__":
    main()
