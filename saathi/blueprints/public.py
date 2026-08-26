"""Public blueprint: token-addressed share card — deliberately login-free.

Unknown token and known-but-disabled token collapse to the SAME 404 so a
guesser learns nothing about which tokens exist (no oracle).
"""

from __future__ import annotations

from flask import Blueprint, abort, render_template
from sqlalchemy import select

from ..extensions import db
from ..models import Profile

bp = Blueprint("public", __name__)


@bp.get("/u/<token>")
def card(token: str) -> str:
    profile = db.session.scalar(
        select(Profile).where(
            Profile.public_token == token,
            Profile.share_enabled.is_(True),
        )
    )
    if profile is None:
        abort(404)
    education = list(profile.user.education_entries)
    work = list(profile.user.work_entries)
    return render_template(
        "public/card.html",
        profile=profile,
        education=education,
        work=work,
    )
