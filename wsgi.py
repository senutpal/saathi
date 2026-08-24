"""WSGI entrypoint: logging is configured here, before the factory import."""

import logging
import os

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
    )

from saathi import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8000)))
