# saathi

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

