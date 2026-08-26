"""Saathi core schema package — re-exports every model.

Deferred tables (owned by their phase, do NOT create early):
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
from .life import Contact, Habit, HabitLog, Mood
from .scheduling import Event, Notification

__all__ = [
    "ActivityLog",
    "Contact",
    "EducationEntry",
    "Event",
    "Habit",
    "HabitLog",
    "Mood",
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
