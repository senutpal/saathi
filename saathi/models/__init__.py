"""Saathi core schema package — re-exports every model.

Deferred tables (owned by their phase, do NOT create early):
LoginAttempt / BackupCode -> P13.
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
from .life import Contact, Expense, Habit, HabitLog, Mood
from .scheduling import CapsuleMessage, Event, Notification

__all__ = [
    "ActivityLog",
    "CapsuleMessage",
    "Contact",
    "EducationEntry",
    "Event",
    "Expense",
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
