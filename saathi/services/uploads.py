"""Secure upload pipeline: extension+size+sniff validation ladder, Pillow
sanitization, thumbnails, per-user storage layout and quota."""

from __future__ import annotations

import io
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import filetype
from flask import current_app
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Upload
from ..utils import log_action

if TYPE_CHECKING:
    from ..models.identity import User

ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "csv", "docx"}
TEXT_ONLY_EXTS = {"txt", "csv"}  # no magic signature exists to sniff
IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
# declared ext -> sniffed filetype kinds accepted (apng shares png magic prefix)
FAMILY_OK = {
    "png": {"png", "apng"},
    "jpg": {"jpg"},
    "jpeg": {"jpg"},
    "gif": {"gif"},
    "webp": {"webp"},
    "pdf": {"pdf"},
    "docx": {"docx"},
}
REENCODE_FORMAT = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}
THUMB_SIZE = (240, 240)
THUMB_SUFFIX = "_240.webp"
SNIFF_HEAD_BYTES = 261
TEXT_SNIFF_BYTES = 8192

logger = logging.getLogger("saathi.uploads")


class UploadRejected(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg


def _user_root(user_id: int) -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"]) / str(user_id)


def user_dir(user_id: int) -> Path:
    root = _user_root(user_id)
    (root / "thumbs").mkdir(parents=True, exist_ok=True)
    return root


def stored_path(user_id: int, stored_filename: str) -> Path:
    return _user_root(user_id) / stored_filename


def thumb_path(user_id: int, stored_filename: str) -> Path:
    stem = stored_filename.rsplit(".", 1)[0]
    return _user_root(user_id) / "thumbs" / f"{stem}{THUMB_SUFFIX}"


def quota_used_bytes(user_id: int) -> int:
    total = db.session.scalar(
        select(func.coalesce(func.sum(Upload.size_bytes), 0)).where(Upload.user_id == user_id)
    )
    return int(total or 0)


def sniff_ext(data: bytes, declared_ext: str) -> tuple[str, bool]:
    """Gate 3: content must confess to the declared family.

    Returns (mime, is_image). txt/csv have no magic bytes, so they fall back
    to a strict UTF-8 decode plus a NUL-byte scan instead.
    """
    kind = filetype.guess(data[:SNIFF_HEAD_BYTES])
    if kind is None:
        if declared_ext not in TEXT_ONLY_EXTS:
            raise UploadRejected("File content doesn't match any allowed type.")
        head = data[:TEXT_SNIFF_BYTES]
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadRejected("Text file is not valid UTF-8.") from exc
        if b"\x00" in head:
            raise UploadRejected("Binary content in a text file.")
        return ("text/csv" if declared_ext == "csv" else "text/plain"), False
    family = FAMILY_OK.get(declared_ext, set())
    if declared_ext not in TEXT_ONLY_EXTS and kind.extension not in family:
        raise UploadRejected(f"Content looks like {kind.mime}, not .{declared_ext}.")
    return kind.mime, kind.extension in IMAGE_EXTS


def verify_image(data: bytes) -> Image.Image:
    """Gate 4: Pillow as validator — format allowlist by magic bytes, full
    decode (fires the decompression-bomb guard). GIF stays byte-identical on
    disk because re-saving kills animation; everything else gets re-encoded."""
    try:
        with Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "GIF", "WEBP"]) as im:
            im.load()
            return im.copy()
    except Image.DecompressionBombError as exc:
        raise UploadRejected("Image dimensions are too large.") from exc
    except Exception as exc:
        raise UploadRejected("That file is not a readable image.") from exc


def make_thumb(im: Image.Image, dest: Path) -> None:
    thumb = im.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(dest, "WEBP", quality=80)


def save_upload(fs: FileStorage, user: User) -> Upload:
    original = secure_filename(fs.filename or "")
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_EXTS:
        raise UploadRejected(f"Extension .{ext or '(none)'} is not allowed.")
    data = fs.read()
    # werkzeug spools big bodies to a temp file it may not close itself;
    # leaving it open surfaces as an unraisable ResourceWarning on Windows
    fs.stream.close()
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise UploadRejected("File exceeds the 5 MB limit.")
    if not data:
        raise UploadRejected("Empty file.")

    mime, is_image = sniff_ext(data, ext)
    if quota_used_bytes(user.id) + len(data) > current_app.config["UPLOAD_QUOTA_BYTES"]:
        raise UploadRejected("Storage quota exceeded — delete some files first.")

    im = verify_image(data) if is_image else None
    if im is not None and ext != "gif":
        # re-encode through a fresh buffer strips EXIF/metadata payloads
        buf = io.BytesIO()
        im.save(buf, REENCODE_FORMAT[ext])
        data = buf.getvalue()

    user_dir(user.id)
    for _ in range(2):  # uuid4 collisions are ~impossible; regenerate once anyway
        stored = f"{uuid.uuid4().hex}.{ext}"
        dest = stored_path(user.id, stored)
        dest.write_bytes(data)
        if im is not None:
            make_thumb(im, thumb_path(user.id, stored))
        row = Upload(
            user_id=user.id,
            original_filename=original,
            stored_filename=stored,
            mime_type=mime,
            size_bytes=len(data),
            is_image=is_image,
        )
        db.session.add(row)
        log_action(user.id, "file_uploaded", original[:120], details=f"{len(data)} bytes")
        try:
            db.session.commit()
            return row
        except IntegrityError:
            db.session.rollback()
            _unlink_quiet(dest)
            _unlink_quiet(thumb_path(user.id, stored))
    raise UploadRejected("Storage collision — please retry.")


def delete_upload(row: Upload) -> None:
    # files first, tolerated failure; a failed unlink must never strand a dead link
    _unlink_retry(stored_path(row.user_id, row.stored_filename))
    _unlink_retry(thumb_path(row.user_id, row.stored_filename))
    log_action(row.user_id, "file_deleted", row.original_filename[:120])
    db.session.delete(row)
    db.session.commit()


def _unlink_quiet(path: Path) -> None:
    path.unlink(missing_ok=True)


def _unlink_retry(path: Path, attempts: int = 3) -> None:
    """Windows AV/indexer handles keep fds alive briefly; back off and let the
    row deletion proceed regardless."""
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt < attempts - 1:
                time.sleep(0.1 * (attempt + 1))
    logger.warning("upload file stayed locked: %s", path)
