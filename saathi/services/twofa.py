"""TOTP two-factor helpers: secrets, backup codes, unified code checking.

Backup codes follow OWASP MFA / NIST 800-63B §5.1.2 "look-up secret"
practice: a small set of opaque random single-use codes stored only as
SHA-256 hashes, riding behind the lockout module.
"""

from __future__ import annotations

import hashlib
import secrets

import pyotp
from sqlalchemy import delete, func, select

from ..extensions import db
from ..models import BackupCode, User
from ..models.base import utcnow

BACKUP_CODE_COUNT = 10


def new_secret() -> str:
    """Base32 shared secret for TOTP provisioning."""
    return pyotp.random_base32()


def provisioning_uri(user: User) -> str:
    """otpauth URI with issuer in BOTH label and param (old+new apps)."""
    return pyotp.TOTP(user.totp_secret or "").provisioning_uri(
        name=user.email, issuer_name="Saathi"
    )


def grouped_secret(secret: str) -> str:
    """Manual-entry form: base32 in 4-char chunks."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def generate_backup_codes() -> list[str]:
    """10 fresh printable codes, collision-free within the batch."""
    codes: set[str] = set()
    while len(codes) < BACKUP_CODE_COUNT:
        codes.add(secrets.token_hex(4).upper())
    return sorted(codes)


def hash_code(raw: str) -> str:
    return hashlib.sha256(raw.strip().upper().encode()).hexdigest()


def store_backup_codes(user: User, codes: list[str]) -> None:
    """Replace the user's set; regeneration invalidates all unused old codes."""
    db.session.execute(delete(BackupCode).where(BackupCode.user_id == user.id))
    db.session.add_all([BackupCode(user_id=user.id, code_hash=hash_code(code)) for code in codes])


def unused_backup_count(user: User) -> int:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(BackupCode)
            .where(BackupCode.user_id == user.id, BackupCode.used_at.is_(None))
        )
        or 0
    )


def consume_backup_code(user: User, raw: str) -> bool:
    """Single-use spend: mark used_at only if still unused."""
    digest = hash_code(raw)
    row = db.session.scalar(
        select(BackupCode).where(
            BackupCode.user_id == user.id,
            BackupCode.code_hash == digest,
            BackupCode.used_at.is_(None),
        )
    )
    if row is None:
        return False
    row.used_at = utcnow()
    db.session.commit()
    return True


def matches_backup_code(user: User, raw: str) -> bool:
    """Existence check WITHOUT spending (disable flow keeps codes usable)."""
    digest = hash_code(raw)
    return (
        db.session.scalar(
            select(BackupCode.id).where(
                BackupCode.user_id == user.id,
                BackupCode.code_hash == digest,
                BackupCode.used_at.is_(None),
            )
        )
        is not None
    )


def verify_login_code(user: User, raw: str) -> bool:
    """The one prompt accepts a fresh TOTP or an unused backup code."""
    if not user.twofa_enabled or not user.totp_secret:
        return False
    normalized = raw.replace(" ", "")
    if pyotp.TOTP(user.totp_secret).verify(normalized, valid_window=1):
        return True
    return consume_backup_code(user, raw)


def verify_existing_code(user: User, raw: str) -> bool:
    """For disable: prove possession without burning a backup code."""
    if not user.totp_secret:
        return False
    normalized = raw.replace(" ", "")
    if pyotp.TOTP(user.totp_secret).verify(normalized, valid_window=1):
        return True
    return matches_backup_code(user, raw)
