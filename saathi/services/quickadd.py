"""Natural-language quick-add: regex-first span isolation, dateparser second.

dateparser happily invents dates from free prose ("call mum march"), so it
never sees raw user text: owned regexes peel leading when-spans first, then
five guards veto weak parses. Anything that fails degrades to a NOTE — still
useful, never silently wrong (B15 §1d).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta

import dateparser

from ..models.base import utcnow
from ..utils import ist_to_utc_naive, utc_to_ist_wall

_ROUTER = re.compile(r"^(rem(?:inder)?|note)\b[\s,:-]*", re.IGNORECASE)

# Tried in order per bite; several bites join into one when-span so
# "tomorrow 6pm" resolves even though no single pattern covers both words.
_WHEN_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"tomorrow\b(?:\s+at\s+(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?)?",
        r"today\b(?:\s+at\s+(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?)?",
        r"next\s+(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b",
        r"(?:on\s+)?(?:mon|tues?|wed(?:nes)?|thur?s?|fri|sat(?:ur)?|sun)[a-z]*\b",
        r"in\s+(\d+)\s+(?:days?|weeks?|hours?|mins?|minutes?)\b",
        r"at\s+(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?\b",
        r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
        r"\d{1,2}/\d{1,2}(?:/\d{2,4})?",
    )
)

# Guard 5: bare month names are not enough — demand a clock time, a day word,
# or an explicit numeric date (dd/mm) before trusting any parse.
_HAS_TIME = re.compile(r"\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|\sat\s", re.IGNORECASE)
_HAS_DAY_WORD = re.compile(
    r"\b(today|tomorrow|next)\b|(?:mon|tues?|wed(?:nes)?|thur?s?|fri|sat(?:ur)?|sun)"
    r"[a-z]*\b|\bin\s+\d+\b",
    re.IGNORECASE,
)
_HAS_NUMERIC_DATE = re.compile(r"\d{1,2}/\d{1,2}")

_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
    "TIMEZONE": "Asia/Kolkata",
}
_MAX_TITLE = 120
_MAX_HORIZON_NO_YEAR = timedelta(days=30)
_MAX_HORIZON_ANY = timedelta(days=365)


def parse_quick_add(
    text: str, *, now_fn: Callable[[], datetime] = utcnow
) -> tuple[str, datetime | None, str]:
    """Return (kind, when_utc_naive_or_None, title). Never raises on input."""
    now = now_fn()
    stripped = text.strip()
    router = _ROUTER.match(stripped)
    wants_reminder = bool(router and router.group(1).lower().startswith("rem"))
    rest = stripped[router.end() :].strip() if router else stripped

    pieces: list[str] = []
    while True:
        for pattern in _WHEN_PATTERNS:
            match = pattern.match(rest)
            if match:
                pieces.append(match.group(0))
                rest = rest[match.end() :].strip(" ,.-")
                break
        else:
            break
    when_text = " ".join(pieces)

    when_utc: datetime | None = None
    if when_text and _is_plausible_when(when_text):
        # RELATIVE_BASE anchors "tomorrow"/"in N days" to the injected clock,
        # not dateparser's real-now (which would make tests non-deterministic)
        base = utc_to_ist_wall(now)
        parsed = dateparser.parse(when_text, settings={**_SETTINGS, "RELATIVE_BASE": base})
        if parsed is not None:
            candidate = ist_to_utc_naive(parsed)
            explicit_date = bool(re.search(r"\d{4}|\d{1,2}/\d{1,2}", when_text))
            horizon = _MAX_HORIZON_ANY if explicit_date else _MAX_HORIZON_NO_YEAR
            if now < candidate <= now + horizon:
                when_utc = candidate

    if wants_reminder and when_utc is not None:
        return "event", when_utc, (rest or "Untitled reminder")[:_MAX_TITLE]
    if wants_reminder:
        return "note", None, (rest or stripped)[:_MAX_TITLE]
    return "note", None, stripped[:_MAX_TITLE]


def _is_plausible_when(when_text: str) -> bool:
    return bool(
        _HAS_TIME.search(when_text)
        or _HAS_DAY_WORD.search(when_text)
        or _HAS_NUMERIC_DATE.search(when_text)
    )
