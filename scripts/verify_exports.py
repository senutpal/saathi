"""One-shot manual-verification helper (P04 DoD: exports verified by opening files).

Run from repo root with the dev environment:
    $env:WEASYPRINT_DLL_DIRECTORIES = "C:\\msys64\\ucrt64\\bin"
    uv run python scripts/verify_exports.py

Seeds the demo user if missing, exports the demo CV as PDF and DOCX into
%TEMP%\\saathi-cv-preview, sanity-checks the magic bytes, and opens both files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from seed_demo import MARKER_EMAIL, run_seed

from saathi import create_app

OUT_DIR = Path.home() / "AppData" / "Local" / "Temp" / "saathi-cv-preview"


def main() -> None:
    app = create_app()
    print(run_seed(app))
    client = app.test_client()

    login_page = client.get("/auth/login").data.decode()
    token = re.search(r'name="csrf_token"[^>]*value="(.+?)"', login_page).group(1)
    client.post(
        "/auth/login",
        data={"email": MARKER_EMAIL, "password": "demo1234", "csrf_token": token},
    )

    OUT_DIR.mkdir(exist_ok=True)
    pdf = client.get("/profile/cv/export.pdf")
    docx = client.get("/profile/cv/export.docx")

    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF", f"pdf failed {pdf.status_code}"
    assert docx.status_code == 200 and docx.data[:4] == b"PK\x03\x04", (
        f"docx failed {docx.status_code}"
    )

    pdf_path = OUT_DIR / "demo-cv.pdf"
    docx_path = OUT_DIR / "demo-cv.docx"
    pdf_path.write_bytes(pdf.data)
    docx_path.write_bytes(docx.data)

    print("PDF :", pdf_path, pdf_path.stat().st_size, "bytes,", pdf.mimetype)
    print("DOCX:", docx_path, docx_path.stat().st_size, "bytes,", docx.mimetype)
    print("disposition:", pdf.headers["Content-Disposition"])
    for path in (pdf_path, docx_path):
        os.startfile(str(path))


if __name__ == "__main__":
    main()
