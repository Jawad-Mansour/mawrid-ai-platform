"""
Feature:  Procurement / Dunning — inbound email detection (replies from suppliers)
Layer:    Infra / Email
Module:   app.infra.email.inbound
Purpose:  Detect supplier replies to our outbound mail (purchase orders, outreach,
          dunning) by polling the operator mailbox over IMAP, then thread + comprehend
          each one. Matching is precise and non-destructive: we only ever read & mark
          \\Seen messages FROM addresses that belong to a known supplier (so the rest
          of the inbox is never touched). The same `ingest_supplier_reply` orchestration
          is reused by the manual "log a reply" endpoint, so pasted replies get the
          identical comprehension + automatic actions:
            • a reply notification on the activity feed,
            • a "changes requested → edit & resend" notification when the supplier asks
              to change the order,
            • an arrival date is auto-tracked as a shipment (importer can still counter
              with a later date).
          IMAP credentials live in Vault at `mawrid/imap` (host/user/password). If they
          are absent, polling is a graceful no-op — the manual path still works.
Depends:  imaplib (stdlib), app.infra.email.comprehend, repos, notifications
HITL:     None directly — drives notifications; order edits / resends stay HITL-gated.
"""

from __future__ import annotations

import asyncio
import contextlib
import email
import imaplib
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from email.utils import parseaddr
from typing import Any

import structlog

from app.infra.email.comprehend import Comprehension, comprehend_reply

logger = structlog.get_logger(__name__)

_PO_RE = re.compile(r"\bPO-\d{6,8}-[A-Z0-9]{4,8}\b", re.IGNORECASE)
_QUOTE_MARKERS = (
    re.compile(r"\nOn .*wrote:", re.IGNORECASE | re.DOTALL),
    re.compile(r"\nFrom: .*", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n-----Original Message-----", re.IGNORECASE),
)


@dataclass
class InboundEmail:
    from_name: str
    from_addr: str
    subject: str
    body: str
    message_id: str | None


# ── IMAP config (best-effort from Vault; absent → polling disabled) ──────────────


def imap_config() -> tuple[str, str, str] | None:
    """Read (host, user, password) from Vault `mawrid/imap`. Returns None if unset."""
    try:
        import hvac  # noqa: PLC0415

        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        resp = client.secrets.kv.v2.read_secret_version(path="mawrid/imap", mount_point="secret")
        data = resp["data"]["data"]
        host = str(data.get("host") or "imap.gmail.com")
        user = data.get("user")
        password = data.get("password")
        if user and password:
            return (host, str(user), str(password))
    except Exception:  # noqa: BLE001 — IMAP is optional; never block on it
        return None
    return None


def inbound_enabled() -> bool:
    return imap_config() is not None


# ── Parsing helpers ──────────────────────────────────────────────────────────────


def _strip_quote(text: str) -> str:
    """Drop the quoted history so comprehension reads only the supplier's new words."""
    cut = len(text)
    for rx in _QUOTE_MARKERS:
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    lines = [ln for ln in text[:cut].splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _body_of(msg: Message) -> str:
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not plain:
                plain = _decode(part)
            elif ctype == "text/html" and not html:
                html = _decode(part)
    else:
        plain = _decode(msg)
    raw = plain or re.sub(r"<[^>]+>", " ", html)
    return _strip_quote(raw)


def _decode(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _parse(msg: Message) -> InboundEmail:
    name, addr = parseaddr(msg.get("From", ""))
    return InboundEmail(
        from_name=name or addr,
        from_addr=(addr or "").lower(),
        subject=str(msg.get("Subject", "")),
        body=_body_of(msg),
        message_id=msg.get("Message-ID"),
    )


def _fetch_blocking(host: str, user: str, password: str, addresses: list[str]) -> list[InboundEmail]:
    """Blocking IMAP fetch — only UNSEEN messages from the given supplier addresses."""
    out: list[InboundEmail] = []
    mailbox = imaplib.IMAP4_SSL(host)
    try:
        mailbox.login(user, password)
        mailbox.select("INBOX")
        seen: set[bytes] = set()
        for addr in addresses[:50]:
            typ, data = mailbox.search(None, "UNSEEN", "FROM", f'"{addr}"')
            if typ != "OK" or not data or not data[0]:
                continue
            for num in data[0].split()[-10:]:
                if num in seen:
                    continue
                seen.add(num)
                ftyp, fdata = mailbox.fetch(num, "(RFC822)")
                if ftyp != "OK" or not fdata or not isinstance(fdata[0], tuple):
                    continue
                raw = fdata[0][1]
                if not isinstance(raw, bytes):
                    continue
                out.append(_parse(email.message_from_bytes(raw)))
                mailbox.store(num, "+FLAGS", "\\Seen")
    finally:
        with contextlib.suppress(Exception):
            mailbox.logout()
    return out


async def fetch_unseen(addresses: list[str]) -> list[InboundEmail]:
    cfg = imap_config()
    if cfg is None or not addresses:
        return []
    host, user, password = cfg
    return await asyncio.to_thread(_fetch_blocking, host, user, password, addresses)


def extract_po_number(subject: str) -> str | None:
    m = _PO_RE.search(subject)
    return m.group(0).upper() if m else None


# ── Shared ingest: thread + comprehend + drive actions ───────────────────────────


async def ingest_supplier_reply(
    session: Any, tenant_id: str, po_id: str, sender: str, body: str
) -> Comprehension:
    """Log an inbound supplier email on a PO thread, comprehend it, and act on it.
    Reused by both the IMAP poller and the manual 'log a reply' endpoint."""
    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415
    from app.infra.db.repos.order_repo import OrderRepository  # noqa: PLC0415
    from app.infra.db.repos.shipment_repo import ShipmentRepository  # noqa: PLC0415

    order_repo = OrderRepository(session, tenant_id)
    po = await order_repo.get_po_by_id(po_id)
    if po is None:
        from app.infra.email.comprehend import _heuristic  # noqa: PLC0415

        return _heuristic(body)

    thread = "\n\n".join(
        f"[{m.get('direction')}] {m.get('sender')}: {m.get('body')}" for m in (po.messages or [])
    )
    c = await comprehend_reply(po_number=po.po_number, thread=thread, latest_message=body)

    await order_repo.append_po_message(
        po_id,
        {
            "direction": "inbound",
            "sender": sender,
            "body": body,
            "at": datetime.now(UTC).isoformat(),
            "extracted": c.as_dict(),
        },
    )
    await order_repo.set_po_status(po_id, "replied")

    # Capture a stated MOQ onto the supplier so future orders respect it.
    if c.min_order_qty:
        from app.infra.db.repos.supplier_repo import SupplierRepository  # noqa: PLC0415

        sup_repo = SupplierRepository(session, tenant_id)
        sup = await sup_repo.get_by_id(po.supplier_id)
        if sup is not None and (sup.moq or 0) != c.min_order_qty:
            await sup_repo.update(po.supplier_id, moq=c.min_order_qty)
            await record_event(
                session, tenant_id, kind="moq_detected",
                title=f"MOQ detected · {po.po_number}",
                body=f"Supplier stated a minimum order quantity of {c.min_order_qty}. Saved to their profile.",
                link="/suppliers",
            )

    await record_event(
        session, tenant_id, kind="supplier_reply",
        title=f"Supplier replied · {po.po_number}",
        body=c.summary or "A supplier reply was received.",
        link=f"/purchase-orders/{po_id}",
    )

    if c.wants_changes:
        await record_event(
            session, tenant_id, kind="order_change_requested",
            title=f"Changes requested · {po.po_number}",
            body=c.change_summary or "The supplier asked to change the order. Review, edit and resend.",
            link=f"/procurement/edit/{po_id}",
        )

    if c.arrival_date:
        ship_repo = ShipmentRepository(session, tenant_id)
        existing = await ship_repo.list_by_po(po_id)
        if existing:
            await ship_repo.update_arrival_date(existing[0].shipment_id, c.arrival_date)
            await ship_repo.update_arrival_at(existing[0].shipment_id, c.arrival_date)
        else:
            await ship_repo.create(
                shipment_id=uuid.uuid4().hex, po_id=po_id,
                expected_arrival_date=c.arrival_date, expected_arrival_at=c.arrival_date,
            )
        await record_event(
            session, tenant_id, kind="arrival_proposed",
            title=f"Arrival date proposed · {po.po_number}",
            body=(
                f"Supplier proposes arrival on {c.arrival_date}. It's now tracked in "
                "Shipments & Arrivals — open the order to accept or suggest a later date."
            ),
            link="/inventory/shipments",
        )

    logger.info("inbound_ingested", po_id=po_id, intent=c.intent, wants_changes=c.wants_changes,
                arrival_date=c.arrival_date)
    return c


async def poll_and_ingest(session_factory: Callable[[], Any]) -> dict[str, int]:
    """Pull unseen supplier replies and ingest them. Matches each email to a PO by the
    PO number in the subject, else to the supplier's most recent PO (by sender address)."""
    from sqlalchemy import func, select  # noqa: PLC0415

    from app.infra.db.models.order import PurchaseOrder  # noqa: PLC0415
    from app.infra.db.models.supplier import Supplier  # noqa: PLC0415
    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415

    if not inbound_enabled():
        return {"enabled": 0, "fetched": 0, "processed": 0}

    # collect supplier addresses across tenants (RLS-superuser in dev; capstone is single-tenant)
    async with session_factory() as session:
        rows = (await session.execute(select(Supplier).where(Supplier.email.is_not(None)))).scalars().all()
        addresses = sorted({(s.email or "").lower() for s in rows if s.email})

    emails = await fetch_unseen(addresses)
    processed = 0
    for em in emails:
        async with session_factory() as session, session.begin():
            target: tuple[str, str] | None = None  # (tenant_id, po_id)
            po_num = extract_po_number(em.subject)
            if po_num:
                row = (
                    await session.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == po_num))
                ).scalars().first()
                if row:
                    target = (row.tenant_id, row.po_id)
            if target is None:
                sup = (
                    await session.execute(
                        select(Supplier).where(func.lower(Supplier.email) == em.from_addr)
                    )
                ).scalars().first()
                if sup:
                    po = (
                        await session.execute(
                            select(PurchaseOrder)
                            .where(
                                PurchaseOrder.tenant_id == sup.tenant_id,
                                PurchaseOrder.supplier_id == sup.supplier_id,
                            )
                            .order_by(PurchaseOrder.created_at.desc())
                        )
                    ).scalars().first()
                    if po:
                        target = (sup.tenant_id, po.po_id)
                    else:
                        # No purchase order — this is an outreach reply. Thread it onto the
                        # supplier's outreach conversation so it shows in the Outreach Inbox.
                        sup.outreach_messages = [
                            *(sup.outreach_messages or []),
                            {"direction": "inbound", "sender": sup.name, "body": em.body,
                             "at": datetime.now(UTC).isoformat()},
                        ]
                        await record_event(
                            session, sup.tenant_id, kind="supplier_reply",
                            title=f"Reply from {sup.name}",
                            body=(em.body[:140] or em.subject),
                            link=f"/suppliers/outreach?supplier={sup.supplier_id}",
                        )
                        processed += 1
                        continue
            if target:
                await ingest_supplier_reply(session, target[0], target[1], em.from_name or em.from_addr, em.body)
                processed += 1

    logger.info("inbound_poll_done", fetched=len(emails), processed=processed)
    return {"enabled": 1, "fetched": len(emails), "processed": processed}
