"""Saathi core schema package — re-exports every model.

Deferred tables (owned by their phase, do NOT create early):
contacts / habits / habit_logs / moods / expenses -> P11 ·
capsule_messages -> P12 · LoginAttempt / BackupCode -> P13.
"""

from .base import TimestampMixin, utcnow
from .content import (
    ActivityLog,
    Note,
    NoteTag,
    SearchCache,
    Tag,
    Upload,
    WeatherCache,
)
from .identity import EducationEntry, Profile, User, WorkEntry
from .scheduling import Event, Notification

__all__ = [
    "ActivityLog",
    "EducationEntry",
    "Event",
    "Note",
    "NoteTag",
    "Notification",
    "Profile",
    "SearchCache",
    "Tag",
    "TimestampMixin",
    "Upload",
    "User",
    "WeatherCache",
    "WorkEntry",
    "utcnow",
]
