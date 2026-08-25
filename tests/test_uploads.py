"""Upload pipeline: rejection ladder, image sanitization, IDOR, lifecycle."""

from __future__ import annotations

import gc
import io
import warnings
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin
from werkzeug.datastructures import FileStorage

from saathi.extensions import db
from saathi.models import Upload
from saathi.services import uploads as svc
from saathi.services.uploads import UploadRejected

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Size 4/Root 1 0 R>>\n%%EOF"
)


def png_bytes(marker: str | None = None) -> bytes:
    buf = io.BytesIO()
    im = Image.new("RGB", (8, 8), (180, 40, 40))
    if marker is not None:
        meta = PngImagePlugin.PngInfo()
        meta.add_text("smuggled", marker)
        im.save(buf, "PNG", pnginfo=meta)
    else:
        im.save(buf, "PNG")
    return buf.getvalue()


def jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 180, 40)).save(buf, "JPEG")
    return buf.getvalue()


def animated_gif_bytes() -> bytes:
    buf = io.BytesIO()
    frames = [Image.new("RGB", (10, 10), color) for color in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], loop=0)
    return buf.getvalue()


def fs(data: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(data), filename=name)


def upload(client, data: bytes, name: str):
    return client.post(
        "/files/upload",
        data={"file": (io.BytesIO(data), name)},
        follow_redirects=False,
    )


def row_id(name: str) -> int:
    return db.session.query(Upload).filter_by(original_filename=name).one().id


def nothing_written(root: str) -> bool:
    base = Path(root)
    return not any(p.is_dir() and any(p.iterdir()) for p in base.iterdir())


def test_anonymous_gallery_redirects_to_login(client):
    response = client.get("/files")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_bad_extension_rejected_and_nothing_written(logged_in_client, app):
    response = upload(logged_in_client, b"MZ fake exe", "evil.exe")

    assert response.status_code == 200
    assert b"not allowed" in response.data
    with app.app_context():
        assert db.session.query(Upload).count() == 0
    assert nothing_written(app.config["UPLOAD_FOLDER"])


def test_polyglot_text_named_png_rejected(logged_in_client, app):
    response = upload(logged_in_client, b"totally not an image", "fake.png")

    assert response.status_code == 200
    assert b"any allowed type" in response.data
    with app.app_context():
        assert db.session.query(Upload).count() == 0


def test_jpeg_content_named_png_rejected_as_family_mismatch(logged_in_client):
    response = upload(logged_in_client, jpeg_bytes(), "renamed.png")

    assert response.status_code == 200
    assert b"image/jpeg" in response.data


def test_valid_txt_accepted_with_plain_mime(logged_in_client, app):
    response = upload(logged_in_client, b"hello saathi\n", "notes.txt")

    assert response.status_code == 302
    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="notes.txt").one()
        assert row.mime_type == "text/plain"
        assert row.is_image is False
        stored = svc.stored_path(row.user_id, row.stored_filename)
        assert stored.read_bytes() == b"hello saathi\n"


@pytest.mark.parametrize("payload", [b"caf\xe9 latin-1", b"nul\x00byte"])
def test_txt_with_non_utf8_or_nul_rejected(logged_in_client, app, payload):
    upload(logged_in_client, payload, "bad.txt")

    with app.app_context():
        assert db.session.query(Upload).count() == 0


def test_png_sanitized_reencoded_and_thumbed(logged_in_client, app):
    response = upload(logged_in_client, png_bytes(marker="payload-marker"), "pic.png")

    assert response.status_code == 302
    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="pic.png").one()
        fid = row.id
        assert row.mime_type == "image/png"
        assert row.is_image is True
        stored = svc.stored_path(row.user_id, row.stored_filename)
        thumb = svc.thumb_path(row.user_id, row.stored_filename)
        assert b"payload-marker" not in stored.read_bytes()
        assert thumb.is_file()

    page = logged_in_client.get("/files")
    assert f"/files/{fid}/thumb".encode() in page.data


def test_decompression_bomb_rejected_cleanly(logged_in_client, app, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 16)

    response = upload(logged_in_client, png_bytes(), "bomb.png")

    assert response.status_code == 200
    assert b"too large" in response.data or b"readable image" in response.data
    with app.app_context():
        assert db.session.query(Upload).count() == 0


def test_oversize_body_returns_413_friendly_page(logged_in_client):
    response = upload(logged_in_client, b"x" * (6 * 1024 * 1024), "big.txt")

    assert response.status_code == 413
    assert b"5 MB" in response.data

    # werkzeug 3.1's multipart parser abandons its spooled temp file when it
    # aborts mid-stream on MAX_CONTENT_LENGTH; collect now so the resulting
    # ResourceWarning stays scoped here instead of failing the NEXT test
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ResourceWarning)
        gc.collect()


def test_service_size_guard_rejects_before_write(app, make_user):
    user = make_user()
    app.config["MAX_CONTENT_LENGTH"] = 10

    with app.app_context():
        with pytest.raises(UploadRejected, match="5 MB"):
            svc.save_upload(fs(png_bytes(), "big.png"), user)


def test_service_rejects_empty_file(app, make_user):
    user = make_user()

    with app.app_context():
        with pytest.raises(UploadRejected, match="Empty"):
            svc.save_upload(fs(b"", "empty.txt"), user)


def test_gif_stored_byte_identical_with_thumb(logged_in_client, app):
    raw = animated_gif_bytes()

    response = upload(logged_in_client, raw, "anim.gif")

    assert response.status_code == 302
    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="anim.gif").one()
        stored = svc.stored_path(row.user_id, row.stored_filename)
        assert row.mime_type == "image/gif"
        assert row.is_image is True
        assert stored.read_bytes() == raw
        assert svc.thumb_path(row.user_id, row.stored_filename).is_file()


def test_pdf_gets_document_treatment_without_thumb(logged_in_client, app):
    response = upload(logged_in_client, MINIMAL_PDF, "doc.pdf")

    assert response.status_code == 302
    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="doc.pdf").one()
        fid = row.id
        assert row.mime_type == "application/pdf"
        assert row.is_image is False

    assert logged_in_client.get(f"/files/{fid}/thumb").status_code == 404
    page = logged_in_client.get("/files")
    assert f"/files/{fid}/thumb".encode() not in page.data


def test_download_serves_attachment_with_original_bytes(logged_in_client, app):
    upload(logged_in_client, png_bytes(), "pic.png")

    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="pic.png").one()
        fid = row.id
        expected = svc.stored_path(row.user_id, row.stored_filename).read_bytes()
        # display-only metadata: prove the RFC 5987 path for non-ASCII names,
        # which secure_filename otherwise flattens at the intake gate
        row.original_filename = "résumé ünïcode.png"
        db.session.commit()

    response = logged_in_client.get(f"/files/{fid}/download")
    disposition = response.headers["Content-Disposition"]

    assert response.status_code == 200
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" in disposition
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.data == expected
    response.close()


def test_conditional_download_returns_304_on_etag(logged_in_client, app):
    upload(logged_in_client, png_bytes(), "etag.png")

    with app.app_context():
        fid = row_id("etag.png")
    first = logged_in_client.get(f"/files/{fid}/download")
    assert first.status_code == 200

    again = logged_in_client.get(
        f"/files/{fid}/download",
        headers={"If-None-Match": first.headers["ETag"]},
    )
    first.close()

    assert again.status_code == 304
    again.close()


def test_cross_user_access_collapses_to_404_everywhere(client, make_user, login, app):
    make_user(username="owner")
    client.post("/auth/login", data={"email": "a@example.com", "password": "correct horse"})
    upload(client, png_bytes(), "secret.png")
    client.post("/auth/logout")
    make_user(email="b@example.com", username="intruder")
    login("b@example.com", "correct horse")

    with app.app_context():
        fid = row_id("secret.png")

    assert client.get(f"/files/{fid}/download").status_code == 404
    assert client.get(f"/files/{fid}/thumb").status_code == 404
    assert client.post(f"/files/{fid}/delete").status_code == 404

    with app.app_context():
        assert db.session.get(Upload, fid) is not None


def test_delete_cleans_row_file_and_thumb_then_404s(logged_in_client, app):
    upload(logged_in_client, png_bytes(), "gone.png")

    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="gone.png").one()
        fid = row.id
        stored = svc.stored_path(row.user_id, row.stored_filename)
        thumb = svc.thumb_path(row.user_id, row.stored_filename)

    response = logged_in_client.post(f"/files/{fid}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert not stored.exists()
    assert not thumb.exists()
    with app.app_context():
        assert db.session.get(Upload, fid) is None
    assert logged_in_client.post(f"/files/{fid}/delete").status_code == 404


def test_locked_files_back_off_but_row_still_deleted(logged_in_client, app, monkeypatch):
    upload(logged_in_client, png_bytes(), "locked.png")

    real_unlink = Path.unlink
    attempts = {"count": 0}

    def flaky_unlink(self, missing_ok=False):
        attempts["count"] += 1
        if attempts["count"] <= 2:
            raise PermissionError
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    monkeypatch.setattr(svc.time, "sleep", lambda _s: None)

    with app.app_context():
        row = db.session.query(Upload).filter_by(original_filename="locked.png").one()
        fid = row.id
        stored = svc.stored_path(row.user_id, row.stored_filename)
        thumb = svc.thumb_path(row.user_id, row.stored_filename)

    response = logged_in_client.post(f"/files/{fid}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert attempts["count"] >= 2
    assert not stored.exists()
    assert not thumb.exists()
    with app.app_context():
        assert db.session.get(Upload, fid) is None


def test_quota_blocks_upload_when_sum_exceeds_cap(logged_in_client, app):
    app.config["UPLOAD_QUOTA_BYTES"] = 10

    response = upload(logged_in_client, png_bytes(), "over.png")

    assert response.status_code == 200
    assert b"quota exceeded" in response.data.lower()
    with app.app_context():
        assert db.session.query(Upload).count() == 0


def test_uuid_collision_regenerates_once(logged_in_client, app, make_user, monkeypatch):
    collide = "a" * 32
    fallback = "b" * 32
    seq = iter([collide, fallback])

    class FakeKind:
        def __init__(self, value):
            self.hex = value

    monkeypatch.setattr(svc.uuid, "uuid4", lambda: FakeKind(next(seq)))

    with app.app_context():
        from saathi.models import User

        owner = db.session.query(User).filter_by(email="a@example.com").one()
        owner_id = owner.id
        db.session.add(
            Upload(
                user_id=owner_id,
                original_filename="seed.png",
                stored_filename=f"{collide}.png",
                mime_type="image/png",
                size_bytes=1,
            )
        )
        db.session.commit()

    response = upload(logged_in_client, png_bytes(), "lucky.png")

    assert response.status_code == 302
    with app.app_context():
        lucky = db.session.query(Upload).filter_by(original_filename="lucky.png").one()
        assert lucky.stored_filename.startswith(fallback)
        assert not svc.thumb_path(owner_id, f"{collide}.png").exists()
        assert svc.thumb_path(owner_id, lucky.stored_filename).is_file()


def test_gallery_orders_newest_first_and_shows_quota(logged_in_client):
    upload(logged_in_client, png_bytes(), "older-one.png")
    upload(logged_in_client, b"newest doc\n", "newer.txt")

    page = logged_in_client.get("/files")
    html = page.data.decode()

    assert page.status_code == 200
    assert html.index("newer.txt") < html.index("older-one.png")
    assert "of 50.0 MiB used" in html
