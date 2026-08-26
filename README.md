# saathi

![CI](https://github.com/senutpal/saathi/actions/workflows/ci.yml/badge.svg)

Saathi ("Here I Am") — a multi-user personal-assistant web app built with Flask, server-rendered.

## Run (dev)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```powershell
uv sync
uv run waitress-serve --host=127.0.0.1 --port=8000 wsgi:app
```

Then open http://127.0.0.1:8000 — health check at `/healthz`.

Configuration comes from `.env` (copy `.env.example`). `FLASK_ENV` switches
environment (`development` / `production`); production refuses to boot without a
strong `SECRET_KEY`.

## Email notifications (optional)

Reminder alerts always land in the in-app bell/inbox. Setting `MAIL_ENABLED=true`
additionally emails them at fire time (best-effort — SMTP failure never loses a
notification). Gmail is the default provider and needs an **app password**:

1. Sign in at myaccount.google.com → Security → turn on **2-Step Verification**
   (the App Passwords screen stays hidden without it).
2. Open myaccount.google.com/apppasswords → name it `saathi-dev` → copy the
   16-character code.
3. `.env`: `MAIL_ENABLED=true`, `MAIL_USERNAME=<full gmail address>`,
   `MAIL_PASSWORD=<16-char code, no spaces>`, `MAIL_PORT=465`.
4. Changing your Google account password silently revokes app passwords —
   if sends start failing with `535 5.7.8`, generate a new one.

Set `APP_URL` (e.g. your deployed URL) so emails contain an absolute link to the inbox.

