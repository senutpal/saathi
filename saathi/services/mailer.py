"""Best-effort fire-time email delivery.

Rung 3 of the notification ladder (B07): the bell row is always committed
first, so SMTP failure can only lose the email, never the notification.
Stdlib smtplib over Flask-Mail — a few sends/day needs no extension.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

from flask import Flask, current_app, render_template
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Notification

log = logging.getLogger("saathi.email")

# bp name == URL prefix (CONVENTIONS §3), so the inbox path is a stable constant;
# url_for would demand SERVER_NAME outside a request context.
INBOX_PATH = "/notifications"


def send_email(to: str, subject: str, html: str, plain: str) -> bool:
    """Send one message via SMTP_SSL; False on disabled-gate or any failure."""
    cfg = current_app.config
    if not cfg["MAIL_ENABLED"]:
        return False
    # header-injection guard: subjects must never carry newlines
    subject = " ".join(str(subject).splitlines())
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_DEFAULT_SENDER"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            cfg["MAIL_SERVER"],
            int(cfg["MAIL_PORT"]),
            timeout=float(cfg["MAIL_TIMEOUT"]),
            context=ctx,
        ) as smtp:
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 — email must never propagate into the ticker
        log.warning("SMTP send failed (%s)", to)
        return False


def enqueue_email(app: Flask, notification_ids: list[int]) -> threading.Thread | None:
    """Spawn a throwaway daemon thread to email the given notifications.

    Returns the thread so tests can join() it; None when gated off or empty.
    """
    if not notification_ids or not app.config["MAIL_ENABLED"]:
        return None
    thread = threading.Thread(
        target=_deliver_all, args=(app, notification_ids), name="email-ladder", daemon=True
    )
    thread.start()
    return thread


def _deliver_all(app: Flask, notification_ids: list[int]) -> None:
    with app.app_context():
        rows = list(
            db.session.scalars(
                select(Notification)
                .where(Notification.id.in_(notification_ids))
                .options(joinedload(Notification.user))
            )
        )
        for notification in rows:
            # one bad row (render error, SMTP outage) must not skip the rest
            try:
                _send_one(notification)
            except Exception:  # noqa: BLE001 — email must never propagate anywhere
                log.exception("email failed for notification %s", notification.id)
            db.session.rollback()  # release the read snapshot after each send


def _send_one(notification: Notification) -> bool:
    link = f"{current_app.config['APP_URL']}{INBOX_PATH}" if current_app.config["APP_URL"] else ""
    html = render_template(
        "emails/notification.html", title=notification.title, body=notification.body, link=link
    )
    plain = f"{notification.title}\n{notification.body}".strip()
    if link:
        plain = f"{plain}\n\nOpen your inbox: {link}"
    return send_email(
        notification.user.email,
        f"Saathi reminder: {notification.title}",
        html,
        plain,
    )
