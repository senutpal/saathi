"""Backup blueprint: JSON export/import plus expenses CSV (thin handlers)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required
from sqlalchemy import select

from ..extensions import db
from ..models import Expense
from ..services.backup import ImportRejected, apply_import, export_payload
from ..utils import csv_safe, log_action

bp = Blueprint("backup", __name__)

MAX_IMPORT_BYTES = 10 * 1024 * 1024


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@bp.get("/backup")
def index() -> str:
    return render_template("backup/index.html")


@bp.get("/export.json")
@login_required
def export_json() -> Response:
    payload = json.dumps(export_payload(current_user), ensure_ascii=False)
    log_action(current_user.id, "backup_exported", "Downloaded full backup")
    db.session.commit()
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        payload,
        mimetype="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=saathi-backup-{stamp}.json",
            # downloads must never execute in the origin's context (sniffing)
            "X-Content-Type-Options": "nosniff",
        },
    )


@bp.get("/export/expenses.csv")
@login_required
def export_expenses_csv() -> ResponseReturnValue:
    rows = list(
        db.session.scalars(
            select(Expense)
            .where(Expense.user_id == current_user.id)
            .order_by(Expense.spent_on.desc(), Expense.id.desc())
        )
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["amount", "currency", "category", "spent_on", "note"])
    for row in rows:
        rupees, paise = divmod(row.amount_cents, 100)
        writer.writerow(
            [
                f"{rupees}.{paise:02d}",
                csv_safe(row.currency),
                csv_safe(row.category),
                row.spent_on.isoformat(),
                csv_safe(row.note or ""),
            ]
        )
    log_action(current_user.id, "backup_exported", f"Exported {len(rows)} expenses as CSV")
    db.session.commit()
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=expenses.csv",
            "X-Content-Type-Options": "nosniff",
        },
    )


@bp.post("/import.json")
def import_json() -> ResponseReturnValue:
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Choose a backup file to restore.", "error")
        return redirect(url_for("backup.index"))
    blob = upload.read(MAX_IMPORT_BYTES + 1)
    if len(blob) > MAX_IMPORT_BYTES:
        abort(413)
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        flash("That file is not valid JSON.", "error")
        current_app.logger.info("import decode failed: %s", exc)
        return redirect(url_for("backup.index"))
    try:
        counts = apply_import(current_user, payload)
    except ImportRejected as reason:
        flash(f"Import rejected: {reason}", "error")
        return redirect(url_for("backup.index"))
    total = sum(counts.values())
    log_action(current_user.id, "backup_imported", f"Restored {total} rows from backup")
    db.session.commit()
    flash(f"Import complete: {total} rows restored.")
    return redirect(url_for("backup.index"))
