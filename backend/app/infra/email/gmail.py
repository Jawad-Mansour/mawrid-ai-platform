"""
Feature:  Connect Gmail — send-as-user + read replies via the Gmail API (per tenant)
Layer:    Infra / Email
Module:   app.infra.email.gmail
Purpose:  Once a tenant connects their Gmail (OAuth), Mawrid can:
            • SEND POs/outreach/dunning through their Gmail (Google DKIM → inbox, not Junk),
            • READ their replies back (poll) to auto-detect/thread/comprehend them.
          No passwords — uses the stored OAuth refresh token. Works for any user who clicks
          "Connect Gmail". OAuth client_id/secret live in Vault at mawrid/google.
Depends:  httpx, app.infra.email.inbound (ingest + helpers), Gmail REST API
HITL:     None directly — drives the same HITL-gated flows; reading is read-only.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly"


def google_config() -> tuple[str, str] | None:
    """(client_id, client_secret) from Vault mawrid/google, or None if not configured."""
    try:
        import hvac  # noqa: PLC0415

        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        data = client.secrets.kv.v2.read_secret_version(path="mawrid/google", mount_point="secret")["data"]["data"]
        cid, csec = data.get("client_id"), data.get("client_secret")
        if cid and csec:
            return (str(cid), str(csec))
    except Exception:  # noqa: BLE001 — optional integration
        return None
    return None


def google_enabled() -> bool:
    return google_config() is not None


# ── OAuth token endpoints ────────────────────────────────────────────────────


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any] | None:
    cfg = google_config()
    if cfg is None:
        return None
    cid, csec = cfg
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(TOKEN_URL, data={
            "code": code, "client_id": cid, "client_secret": csec,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        })
    if r.status_code != 200:  # noqa: PLR2004
        logger.warning("google_code_exchange_failed", status=r.status_code, body=r.text[:300])
        return None
    return dict(r.json())


async def access_token_from_refresh(refresh_token: str) -> str | None:
    cfg = google_config()
    if cfg is None:
        return None
    cid, csec = cfg
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(TOKEN_URL, data={
            "refresh_token": refresh_token, "client_id": cid, "client_secret": csec,
            "grant_type": "refresh_token",
        })
    if r.status_code != 200:  # noqa: PLR2004
        logger.warning("google_token_refresh_failed", status=r.status_code, body=r.text[:300])
        return None
    return str(r.json().get("access_token") or "") or None


async def get_email_address(access_token: str) -> str | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{GMAIL_API}/profile", headers={"Authorization": f"Bearer {access_token}"})
    return str(r.json().get("emailAddress") or "") or None if r.status_code == 200 else None  # noqa: PLR2004


# ── Send as the connected user ───────────────────────────────────────────────


async def send_via_gmail(
    access_token: str, *, to: str, subject: str, body: str, from_email: str,
    attachment_bytes: bytes | None = None, attachment_filename: str | None = None,
    attachment_mime: str = "application/pdf",
) -> bool:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = from_email
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment_bytes and attachment_filename:
        maintype, _, subtype = attachment_mime.partition("/")
        msg.add_attachment(attachment_bytes, maintype=maintype or "application", subtype=subtype or "octet-stream", filename=attachment_filename)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": raw},
        )
    if r.status_code not in (200, 202):  # noqa: PLR2004
        logger.warning("gmail_send_failed", status=r.status_code, body=r.text[:300])
        return False
    logger.info("gmail_sent", to=to, subject=subject)
    return True


async def send_email_for_tenant(
    session: Any, tenant_id: str, *, to: str, subject: str, body: str, **kwargs: Any
) -> str | None:
    """Send through the tenant's connected Gmail if they have one (best deliverability),
    else fall back to SendGrid. Used everywhere Mawrid emails a supplier/customer."""
    from app.infra.db.models.gmail import GmailConnection  # noqa: PLC0415
    from app.infra.email.sender import send_email  # noqa: PLC0415

    conn = await session.get(GmailConnection, tenant_id)
    if conn is not None:
        token = await access_token_from_refresh(conn.refresh_token)
        if token:
            ok = await send_via_gmail(
                token, to=to, subject=subject, body=body, from_email=conn.email,
                attachment_bytes=kwargs.get("attachment_bytes"),
                attachment_filename=kwargs.get("attachment_filename"),
                attachment_mime=kwargs.get("attachment_mime", "application/pdf"),
            )
            if ok:
                return "gmail"
    return await send_email(to=to, subject=subject, body=body, **kwargs)


class TenantEmailSender:
    """Protocol-compatible email sender that routes through the tenant's connected Gmail
    when available, else SendGrid. Drop-in for the HITL approval path."""

    def __init__(self, session: Any, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def send(self, to: str, subject: str, body: str, **kwargs: Any) -> str | None:
        return await send_email_for_tenant(self._session, self._tenant_id, to=to, subject=subject, body=body, **kwargs)


# ── Read replies ─────────────────────────────────────────────────────────────


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")


def _extract_body(payload: dict[str, Any]) -> str:
    from app.infra.email.inbound import _strip_quote  # noqa: PLC0415

    mime = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    if mime == "text/plain" and body.get("data"):
        return _strip_quote(_decode(str(body["data"])))
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and (part.get("body") or {}).get("data"):
            return _strip_quote(_decode(str(part["body"]["data"])))
    for part in payload.get("parts", []) or []:
        sub = _extract_body(part)
        if sub:
            return sub
    if mime == "text/html" and body.get("data"):
        return _strip_quote(re.sub(r"<[^>]+>", " ", _decode(str(body["data"]))))
    return ""


def _parse_gmail_message(msg: dict[str, Any]) -> dict[str, str]:
    payload = msg.get("payload", {}) or {}
    headers = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in payload.get("headers", [])}
    name, addr = parseaddr(headers.get("from", ""))
    return {
        "from_addr": (addr or "").lower(),
        "from_name": name or addr or "",
        "subject": headers.get("subject", ""),
        "body": _extract_body(payload),
    }


async def list_replies(access_token: str, addresses: list[str], newer_than_days: int = 3) -> list[dict[str, str]]:
    """Unread messages FROM the given supplier addresses (then marked read). Non-destructive
    to the rest of the inbox — only touches mail from known suppliers."""
    if not addresses:
        return []
    from_clause = " OR ".join(f"from:{a}" for a in addresses[:50])
    q = f"is:unread newer_than:{newer_than_days}d ({from_clause})"
    out: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        hdr = {"Authorization": f"Bearer {access_token}"}
        lr = await client.get(f"{GMAIL_API}/messages", headers=hdr, params={"q": q, "maxResults": "20"})
        if lr.status_code != 200:  # noqa: PLR2004
            return []
        ids = [str(m["id"]) for m in lr.json().get("messages", []) if m.get("id")]
        for mid in ids:
            mr = await client.get(f"{GMAIL_API}/messages/{mid}", headers=hdr, params={"format": "full"})
            if mr.status_code != 200:  # noqa: PLR2004
                continue
            parsed = _parse_gmail_message(mr.json())
            parsed["id"] = mid
            out.append(parsed)
            await client.post(f"{GMAIL_API}/messages/{mid}/modify", headers=hdr, json={"removeLabelIds": ["UNREAD"]})
    return out


async def gmail_poll_and_ingest(session_factory: Callable[[], Any]) -> dict[str, int]:
    """For every tenant with a connected Gmail, pull supplier replies via the Gmail API and
    ingest them (thread + comprehend) — the same pipeline as the manual/IMAP paths."""
    from sqlalchemy import func, select  # noqa: PLC0415

    from app.infra.db.models.gmail import GmailConnection  # noqa: PLC0415
    from app.infra.db.models.order import PurchaseOrder  # noqa: PLC0415
    from app.infra.db.models.supplier import Supplier  # noqa: PLC0415
    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415
    from app.infra.email.inbound import extract_po_number, ingest_supplier_reply  # noqa: PLC0415

    async with session_factory() as session:
        conns = (await session.execute(select(GmailConnection))).scalars().all()
        targets = [(c.tenant_id, c.refresh_token) for c in conns]
    if not targets:
        return {"enabled": 0, "processed": 0}

    processed = 0
    for tenant_id, refresh in targets:
        token = await access_token_from_refresh(refresh)
        if not token:
            continue
        async with session_factory() as session:
            sups = (await session.execute(select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.email.is_not(None)))).scalars().all()
            addresses = sorted({(s.email or "").lower() for s in sups if s.email})
        from datetime import UTC, datetime  # noqa: PLC0415

        for em in await list_replies(token, addresses):
            async with session_factory() as session, session.begin():
                po_id: str | None = None
                po_num = extract_po_number(em["subject"])
                if po_num:
                    row = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_number == po_num))).scalars().first()
                    if row:
                        po_id = row.po_id
                if po_id is None:
                    sup = (await session.execute(select(Supplier).where(Supplier.tenant_id == tenant_id, func.lower(Supplier.email) == em["from_addr"]))).scalars().first()
                    if sup:
                        po = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.supplier_id == sup.supplier_id).order_by(PurchaseOrder.created_at.desc()))).scalars().first()
                        if po:
                            po_id = po.po_id
                        else:
                            sup.outreach_messages = [*(sup.outreach_messages or []), {"direction": "inbound", "sender": sup.name, "body": em["body"], "at": datetime.now(UTC).isoformat()}]
                            await record_event(session, tenant_id, kind="supplier_reply", title=f"Reply from {sup.name}", body=(em["body"][:140] or em["subject"]), link=f"/suppliers/outreach?supplier={sup.supplier_id}")
                            processed += 1
                            continue
                if po_id:
                    await ingest_supplier_reply(session, tenant_id, po_id, em["from_name"] or em["from_addr"], em["body"])
                    processed += 1

    logger.info("gmail_poll_done", tenants=len(targets), processed=processed)
    return {"enabled": 1, "processed": processed}
