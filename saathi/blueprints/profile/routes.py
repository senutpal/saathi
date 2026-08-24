"""Profile routes: personal-data view/edit plus education/work entry CRUD and CV."""

from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

from flask import (
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    send_file,
    url_for,
)
from flask_login import current_user

from ...extensions import db
from ...models import EducationEntry, Profile, Upload, WorkEntry
from ...services.cv import build_cv_context, resolve_theme, slugify
from ...utils import get_own_or_404, log_action
from . import bp
from .forms import EducationForm, ProfileForm, WorkForm

try:
    # Eager probe: a missing-Pango OSError surfaces at boot, never mid-request.
    from weasyprint import CSS, HTML

    HAS_WEASYPRINT = True
except (OSError, ImportError):  # OSError = missing Pango DLLs on Windows
    HAS_WEASYPRINT = False

try:
    from docxtpl import DocxTemplate

    HAS_DOCXTPL = True
except ImportError:
    HAS_DOCXTPL = False


def _current_profile() -> Profile:
    prof = current_user.profile
    if prof is None:
        prof = Profile(user_id=current_user.id)
        db.session.add(prof)
    return prof


def _flash_form_errors(form: EducationForm | WorkForm | ProfileForm) -> None:
    for messages in form.errors.values():
        for message in messages:
            flash(message, "error")


@bp.get("")
def view() -> str:
    return render_template(
        "profile/view.html",
        profile=current_user.profile,
        education_form=EducationForm(),
        work_form=WorkForm(),
    )


@bp.route("/edit", methods=["GET", "POST"])
def edit() -> str | Response:
    form = ProfileForm(obj=current_user.profile)
    if form.validate_on_submit():
        prof = _current_profile()
        form.populate_obj(prof)
        prof.full_name = prof.full_name.strip()
        db.session.commit()
        flash("Profile saved.")
        return redirect(url_for("profile.view"))
    return render_template("profile/edit.html", form=form)


@bp.post("/education/new")
def education_new() -> Response:
    form = EducationForm()
    if form.validate_on_submit():
        db.session.add(_education_entry(form))
        db.session.commit()
        flash("Education entry added.")
    else:
        _flash_form_errors(form)
    return redirect(url_for("profile.view"))


@bp.post("/education/<int:eid>/delete")
def education_delete(eid: int) -> Response:
    entry = get_own_or_404(EducationEntry, eid)
    db.session.delete(entry)
    db.session.commit()
    flash("Education entry deleted.")
    return redirect(url_for("profile.view"))


@bp.post("/work/new")
def work_new() -> Response:
    form = WorkForm()
    if form.validate_on_submit():
        db.session.add(_work_entry(form))
        db.session.commit()
        flash("Work entry added.")
    else:
        _flash_form_errors(form)
    return redirect(url_for("profile.view"))


@bp.post("/work/<int:wid>/delete")
def work_delete(wid: int) -> Response:
    entry = get_own_or_404(WorkEntry, wid)
    db.session.delete(entry)
    db.session.commit()
    flash("Work entry deleted.")
    return redirect(url_for("profile.view"))


@bp.get("/cv")
def cv_preview() -> str | tuple[str, int]:
    ctx = build_cv_context(current_user)
    if ctx is None:
        return render_template("errors/cv_empty.html"), 409
    theme = resolve_theme()
    return render_template(
        f"cv/themes/{theme}.html.jinja",
        mode="screen",
        theme=theme,
        has_pdf=HAS_WEASYPRINT,
        has_docx=HAS_DOCXTPL,
        **ctx,
    )


@bp.get("/cv/export.pdf")
def export_pdf() -> Response | tuple[str, int]:
    if not HAS_WEASYPRINT:
        flash("PDF export unavailable on this server — use Print / Save as PDF.", "error")
        return redirect(url_for("profile.cv_preview"))
    ctx = build_cv_context(current_user)
    if ctx is None:
        return render_template("errors/cv_empty.html"), 409
    theme = resolve_theme()
    html = render_template(
        f"cv/themes/{theme}.html.jinja",
        mode="print",
        theme=theme,
        has_pdf=True,
        has_docx=HAS_DOCXTPL,
        **ctx,
    )
    pdf_bytes = HTML(string=html, base_url=str(current_app.root_path)).write_pdf(
        stylesheets=[CSS(str(_print_css_path()))]
    )
    return _send_cv_export(ctx["name"], pdf_bytes, "pdf", "application/pdf", theme)


@bp.get("/cv/export.docx")
def export_docx() -> Response | tuple[str, int]:
    if not HAS_DOCXTPL:
        flash("DOCX export unavailable on this server.", "error")
        return redirect(url_for("profile.cv_preview"))
    ctx = build_cv_context(current_user)
    if ctx is None:
        return render_template("errors/cv_empty.html"), 409
    theme = resolve_theme()
    template = DocxTemplate(Path(current_app.root_path) / "templates_docx" / "cv_template.docx")
    template.render(
        {
            **ctx,
            "generated_at_text": ctx["generated_at"].strftime("%d %b %Y"),
            "likes_text": "\n".join(ctx["likes"]),
            "dislikes_text": "\n".join(ctx["dislikes"]),
        }
    )
    buffer = io.BytesIO()
    template.save(buffer)
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return _send_cv_export(ctx["name"], buffer.getvalue(), "docx", docx_mime, theme)


def _print_css_path() -> Path:
    return Path(current_app.root_path) / "static" / "css" / "cv_print.css"


def _send_cv_export(name: str, payload: bytes, extension: str, mime: str, theme: str) -> Response:
    """Persist an id-addressable copy under uploads/cv/<uid>/ then stream the bytes.

    Storage uses a uuid name (never the pretty one); the Upload row + audit log
    share the commit so a rollback cannot leave phantom artifacts (ADR-018).
    """
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "cv" / str(current_user.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.{extension}"
    (folder / stored_name).write_bytes(payload)
    db.session.add(
        Upload(
            user_id=current_user.id,
            original_filename=f"{slugify(name)}-cv.{extension}",
            stored_filename=stored_name,
            mime_type=mime,
            size_bytes=len(payload),
        )
    )
    log_action(current_user.id, "cv_export", f"Exported CV ({extension}/{theme})")
    db.session.commit()
    return send_file(
        io.BytesIO(payload),
        mimetype=mime,
        as_attachment=True,
        download_name=f"{slugify(name)}_cv.{extension}",
    )


def _education_entry(form: EducationForm) -> EducationEntry:
    return EducationEntry(
        user_id=current_user.id,
        institution=form.institution.data.strip(),
        qualification=form.qualification.data.strip(),
        field_of_study=form.field_of_study.data,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        description=form.description.data,
    )


def _work_entry(form: WorkForm) -> WorkEntry:
    return WorkEntry(
        user_id=current_user.id,
        organization=form.organization.data.strip(),
        role=form.role.data.strip(),
        location=form.location.data,
        start_date=form.start_date.data,
        end_date=form.end_date.data,
        description=form.description.data,
    )
