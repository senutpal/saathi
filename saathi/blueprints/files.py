"""Files blueprint: private uploads, gallery grid, owner-checked downloads."""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from sqlalchemy import select
from wtforms import SubmitField

from ..extensions import db
from ..models import Upload
from ..services.uploads import (
    UploadRejected,
    delete_upload,
    quota_used_bytes,
    save_upload,
    stored_path,
    thumb_path,
)
from ..utils import get_own_or_404

bp = Blueprint("files", __name__, url_prefix="/files")


class UploadForm(FlaskForm):
    """Validation of size/extension/content lives in the service, not here —
    FileStorage has no replayable .data and the ladder must stay reusable
    for the seeder and future multi-file loops."""

    file = FileField("File", validators=[FileRequired(message="Choose a file.")])
    submit = SubmitField("Upload")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))


@bp.get("")
def gallery() -> str:
    files = db.session.scalars(
        select(Upload)
        .where(Upload.user_id == current_user.id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
    ).all()
    used = quota_used_bytes(current_user.id)
    return render_template(
        "files/index.html",
        files=files,
        used=used,
        quota=current_app.config["UPLOAD_QUOTA_BYTES"],
    )


@bp.route("/upload", methods=["GET", "POST"])
def upload() -> ResponseReturnValue:
    form = UploadForm()
    if form.validate_on_submit():
        try:
            save_upload(form.file.data, current_user)
            flash("File uploaded.")
            return redirect(url_for("files.gallery"))
        except UploadRejected as exc:
            form.file.errors.append(exc.msg)
    return render_template("files/upload.html", form=form)


@bp.get("/<int:fid>/download")
def download(fid: int) -> ResponseReturnValue:
    """The ONLY way bytes leave the server — DB-derived path, attachment always."""
    row = get_own_or_404(Upload, fid)
    path = stored_path(row.user_id, row.stored_filename)
    if not path.is_file():
        abort(404)
    response = send_file(
        path,
        mimetype=row.mime_type,
        as_attachment=True,
        download_name=row.original_filename,
        conditional=True,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.get("/<int:fid>/thumb")
def thumb(fid: int) -> ResponseReturnValue:
    row = get_own_or_404(Upload, fid)
    if not row.is_image:
        abort(404)
    path = thumb_path(row.user_id, row.stored_filename)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype="image/webp", conditional=True)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/<int:fid>/delete")
def delete(fid: int) -> ResponseReturnValue:
    row = get_own_or_404(Upload, fid)
    delete_upload(row)
    flash("File deleted.")
    return redirect(url_for("files.gallery"))
