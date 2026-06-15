"""
Feature:  Dunning Engine / Procurement / Storefront (cross-cutting)
Layer:    Infra / Email
Module:   app.infra.email.sender
Purpose:  Email client (SendGrid REST API via httpx). Sends: dunning messages
          (Tracks 1-4), purchase orders to suppliers, fulfillment notifications
          to consumers, and invoice PDF attachments. All sends happen after HITL
          approval — this module is called only from HITL action execution paths.
          B2B: email only in capstone (WhatsApp in Wave 1).
          B2C: email + SMS in capstone (WhatsApp in Wave 1).
Depends:  httpx, app.infra.secrets.vault
HITL:     None — this IS the execution layer called after HITL approval.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

from app.infra.secrets.vault import get_secrets

logger = structlog.get_logger(__name__)

_SENDGRID_API = "https://api.sendgrid.com/v3/mail/send"


async def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    from_name: str | None = None,
    html_body: str | None = None,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
    attachment_mime: str = "application/pdf",
) -> None:
    """
    Send an email via SendGrid REST API. Raises on non-2xx status.
    The from-address defaults to the configured verified sender
    (SENDGRID_FROM_EMAIL) — SendGrid rejects unverified senders.
    """
    from app.core.config import get_settings  # noqa: PLC0415

    secrets = get_secrets()
    settings = get_settings()
    api_key = secrets.sendgrid_api_key
    from_email = from_email or settings.sendgrid_from_email
    from_name = from_name or settings.sendgrid_from_name

    content: list[dict[str, str]] = [{"type": "text/plain", "value": body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})

    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to}], "subject": subject}],
        "from": {"email": from_email, "name": from_name},
        "content": content,
    }

    if attachment_bytes and attachment_filename:
        payload["attachments"] = [
            {
                "content": base64.b64encode(attachment_bytes).decode(),
                "filename": attachment_filename,
                "type": attachment_mime,
            }
        ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _SENDGRID_API,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code not in (200, 202):
        logger.error(
            "sendgrid_error",
            status=response.status_code,
            body=response.text[:500],
        )
        response.raise_for_status()

    logger.info("email_sent", to=to, subject=subject)


class EmailSender:
    """Protocol-compatible wrapper around send_email. Usable as a dependency."""

    async def send(self, to: str, subject: str, body: str, **kwargs: Any) -> None:
        await send_email(to=to, subject=subject, body=body, **kwargs)
