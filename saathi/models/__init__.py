"""Saathi core schema package — re-exports every model.

Deferred tables (owned by their phase, do NOT create early):
weather_cache / search_cache -> P09 · contacts / habits / habit_logs / moods /
expenses -> P11 · capsule_messages -> P12 · LoginAttempt / BackupCode -> P13.
"""

from .base import TimestampMixin, utcnow
from .content import ActivityLog, Note, NoteTag, Tag, Upload
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
    "Tag",
    "TimestampMixin",
    "Upload",
    "User",
    "WorkEntry",
    "utcnow",
]
