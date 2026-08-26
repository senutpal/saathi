"""One-user JSON export/import (schema saathi-v1).

EXPORT LAW (B17 P1 — CRITICAL): every query below is scoped to the owning
user; a single unscoped SELECT would turn the backup feature into a
cross-account breach. test_backup.py's leak probe is the CI gate for this.

IMPORT LAW: payload user_ids are never trusted — every inserted row gets
``user_id = importer.id`` regardless of content, and all inserts share ONE
transaction so any bad row rolls back everything (atomicity proof test).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    ActivityLog,
    Contact,
    EducationEntry,
    Event,
    Expense,
    Habit,
    HabitLog,
    Mood,
    Note,
    NoteTag,
    Profile,
    Tag,
    WorkEntry,
)

SCHEMA_VERSION = "saathi-v1"

# Parents before children so FK targets exist when their rows flush.
TABLE_ORDER: tuple[type[db.Model], ...] = (
    Profile,
    Contact,
    Habit,
    HabitLog,
    Mood,
    Expense,
    EducationEntry,
    WorkEntry,
    Event,
    Note,
    Tag,
    NoteTag,
    ActivityLog,
)

# Columns whose value the importer derives itself (never read from payload).
DERIVED_COLUMNS = frozenset({"id", "user_id"})

# Per-table columns excluded from BOTH directions: a live share token copied
# into another account would collide with its UNIQUE constraint and enable
# cross-account link squatting; sharing is opt-in state, not portable content.
STRIPPED_COLUMNS: dict[str, frozenset[str]] = {
    "profiles": frozenset({"public_token", "share_enabled"}),
}

# Child FKs remapped through the fresh parent ids.
FK_REMAPS: dict[str, tuple[str, ...]] = {
    "HabitLog": ("habit_id",),
    "Note": ("event_id",),
    "NoteTag": ("note_id", "tag_id"),
    "ActivityLog": ("event_id",),
}


class ImportRejected(Exception):
    """Raised with a human-readable reason; the caller rolls back atomically."""


# Child tables without their own user_id column, scoped through the parent.
CHILD_SCOPES: dict[type[db.Model], tuple[type[db.Model], str]] = {
    HabitLog: (Habit, "habit_id"),
    NoteTag: (Note, "note_id"),
}


def _rows_scoped(model: type[db.Model], user_id: int):
    """The only sanctioned query shape in this module: user-filtered."""
    if model in CHILD_SCOPES:
        parent, fk = CHILD_SCOPES[model]
        stmt = (
            select(model)
            .join(parent, getattr(model, fk) == parent.id)
            .where(parent.user_id == user_id)
        )
        return db.session.scalars(stmt).all()
    stmt = select(model).where(model.user_id == user_id)
    return db.session.scalars(stmt).all()


def _serialize(row: db.Model) -> dict:
    stripped = STRIPPED_COLUMNS.get(row.__tablename__, frozenset())
    out: dict = {}
    for column in row.__table__.columns:
        if column.name in stripped:
            continue
        value = getattr(row, column.name)
        if isinstance(value, (date, datetime)):
            out[column.name] = value.isoformat()
        else:
            out[column.name] = value
    return out


def export_payload(user) -> dict:
    tables: dict[str, list[dict]] = {}
    for model in TABLE_ORDER:
        rows = _rows_scoped(model, user.id)
        tables[model.__tablename__] = [_serialize(r) for r in rows]
    return {
        "schema": SCHEMA_VERSION,
        "exported_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "user": user.username,
        "_meta": {
            "uploads": "metadata rows are excluded — binary files live outside backups",
            "notes": "ids are retained for FK integrity; the importer renumbers them",
        },
        "tables": tables,
    }


def _validate_value(column, raw, table: str, index: int):
    label = f"{table}[{index}].{column.name}"
    py_type = column.type.python_type
    if raw is None:
        if not column.nullable:
            raise ImportRejected(f"{label}: required value missing")
        return None
    if py_type is bool:
        if not isinstance(raw, bool):
            raise ImportRejected(f"{label}: expected boolean")
        return raw
    if py_type is int:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ImportRejected(f"{label}: expected integer")
        return raw
    if py_type is date:
        try:
            return date.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise ImportRejected(f"{label}: expected ISO date") from exc
    if py_type is datetime:
        try:
            return datetime.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise ImportRejected(f"{label}: expected ISO datetime") from exc
    if not isinstance(raw, str):
        raise ImportRejected(f"{label}: expected string")
    return raw


def _check_schema(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_VERSION:
        raise ImportRejected(f"unsupported schema — expected {SCHEMA_VERSION}")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ImportRejected("'tables' object missing")
    known = {m.__tablename__ for m in TABLE_ORDER}
    unknown = set(tables) - known
    if unknown:
        raise ImportRejected(f"unknown table key(s): {', '.join(sorted(unknown))}")
    return tables


def apply_import(user, payload: dict) -> dict[str, int]:
    """Validate + insert inside one transaction; returns per-table counts.

    Raises ImportRejected (after rollback) for schema/type/FK problems;
    unexpected exceptions propagate after rollback too.
    """
    tables = _check_schema(payload)
    id_maps: dict[str, dict[int, int]] = {}
    counts: dict[str, int] = {}

    try:
        for model in TABLE_ORDER:
            rows = tables.get(model.__tablename__) or []
            if not isinstance(rows, list):
                raise ImportRejected(f"{model.__tablename__}: expected a list of rows")
            columns = {c.name: c for c in model.__table__.columns}
            stripped = STRIPPED_COLUMNS.get(model.__tablename__, frozenset())
            fk_targets = FK_REMAPS.get(model.__name__, ())
            id_map: dict[int, int] = {}
            inserted: list[db.Model] = []

            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ImportRejected(f"{model.__tablename__}[{index}]: row must be an object")
                unknown_keys = set(row) - set(columns)
                if unknown_keys:
                    raise ImportRejected(
                        f"{model.__tablename__}[{index}]: unknown field(s) "
                        f"{', '.join(sorted(unknown_keys))}"
                    )
                data = {}
                if "user_id" in columns:
                    data["user_id"] = user.id
                for name, column in columns.items():
                    if name in DERIVED_COLUMNS or name in stripped:
                        continue
                    raw = row.get(name)
                    if raw is None and column.server_default is not None:
                        continue  # absent stamps fall back to DB defaults
                    if name in fk_targets:
                        # parents precede children in TABLE_ORDER, so their
                        # id map exists right here; unresolved refs reject
                        old_ref = row.get(name)
                        if old_ref is None and column.nullable:
                            data[name] = None
                            continue
                        target_map = id_maps.get(_fk_table(model, name), {})
                        new_ref = target_map.get(old_ref)
                        if new_ref is None:
                            raise ImportRejected(
                                f"{model.__tablename__}[{index}]: dangling {name}={old_ref}"
                            )
                        data[name] = new_ref
                        continue
                    data[name] = _validate_value(column, row.get(name), model.__tablename__, index)
                instance = model(**data)
                db.session.add(instance)
                inserted.append((row.get("id"), instance))

            try:
                db.session.flush()
            except IntegrityError as exc:
                db.session.rollback()
                raise ImportRejected(
                    f"{model.__tablename__}: row violates a data constraint"
                ) from exc
            for old_id, instance in inserted:
                # ids are optional in the payload; a child referencing an
                # unmapped one is rejected by the dangling-FK check above
                if old_id is not None:
                    id_map[old_id] = instance.id

            id_maps[model.__tablename__] = id_map
            counts[model.__tablename__] = len(inserted)
    except Exception:
        db.session.rollback()
        raise

    db.session.commit()
    return counts


def _fk_table(model: type[db.Model], fk_name: str) -> str:
    column = model.__table__.columns[fk_name]
    return list(column.foreign_keys)[0].column.table.name
