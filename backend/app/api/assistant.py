"""
Feature:  AI Assistant (Intelligence)
Layer:    API / Router
Module:   app.api.assistant
Purpose:  One chatbot, two roles selected per message:
            - advisor: business/financial advice & decisions, grounded on a live snapshot
              of the tenant's operation.
            - command_center: factual Q&A over the tenant's REAL data ("how many fridges
              vs toasters", quantities, totals) from a compact data summary.
          Multilingual (EN/FR/AR). GPT-4o backed.
Depends:  app.infra.llm.openai, the tenant's products/suppliers/orders/shipments tables.
HITL:     None — advisory only; it never sends or writes anything.
"""

from __future__ import annotations

import contextlib
from typing import Any

import structlog
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.models.order import PurchaseOrder, Shipment
from app.infra.db.models.product import Product
from app.infra.db.models.supplier import Supplier
from app.infra.llm.openai import chat_completion

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])

_LANG = {"en": "English", "fr": "French", "ar": "Arabic"}


def _money(val: Any, currency: str | None) -> str:
    """Format a numeric amount with its currency, or '' if missing/invalid."""
    if val is None:
        return ""
    with contextlib.suppress(TypeError, ValueError):
        return f"{float(val):.2f} {currency or 'USD'}"
    return ""


def _specs(specs: dict[str, Any] | None) -> str:
    """Flatten the specifications dict to 'key: value; key: value' — this is what lets the
    assistant answer detail questions (dimensions, capacity, colour, weight, material …)."""
    if not specs:
        return ""
    parts: list[str] = []
    for k, v in specs.items():
        if v is None or v == "":
            continue
        vs = ", ".join(str(x) for x in v) if isinstance(v, list | tuple) else str(v)
        vs = vs.replace("\n", " ").strip()
        if vs:
            parts.append(f"{k}: {vs}")
    return "; ".join(parts)


async def _snapshot(session: Any, tenant_id: str) -> tuple[str, str]:
    """Return (summary, detail). Rebuilt LIVE on every message, so anything that just changed
    is reflected immediately. `detail` carries EVERY field of every product (full description +
    all specs), supplier, purchase order, shipment/tracking, dunning/invoice, HITL action and
    recent activity — so the command-center role can answer ANY factual question, in any detail."""
    prods = (
        await session.execute(select(Product).where(Product.tenant_id == tenant_id).limit(400))
    ).scalars().all()
    cats: dict[str, int] = {}
    total_stock = 0
    low = 0
    published = 0
    enriched = 0
    lines: list[str] = []
    for p in prods:
        specs = p.specifications or {}
        cat = str(specs.get("Type") or specs.get("Category") or specs.get("Brand") or "other")
        cats[cat] = cats.get(cat, 0) + 1
        total_stock += p.qty_in_stock
        threshold = p.reorder_threshold if p.reorder_threshold is not None else 5
        if p.qty_in_stock <= threshold:
            low += 1
        if p.storefront_status == "published":
            published += 1
        if p.enrichment_status == "enriched":
            enriched += 1
        last_price = ""
        hist = p.price_history or []
        if hist and isinstance(hist[-1], dict) and hist[-1].get("price") is not None:
            last_price = _money(hist[-1]["price"], p.currency)
        retail = _money(p.retail_price, p.currency)
        desc = (p.description or "").replace("\n", " ").strip()
        if len(desc) > 700:
            desc = desc[:700] + "…"
        sup_txt = ", ".join(str(x) for x in (p.supplier_names or [])) if p.supplier_names else ""
        seg = [
            f"- {p.product_name} [sku {p.sku or '—'}{', barcode ' + p.barcode if p.barcode else ''}]",
            f"type {cat}",
            f"enrichment {p.enrichment_status}/{p.enrichment_confidence or '—'}",
            f"stock {p.qty_in_stock} (published {p.storefront_qty}, reorder ≤ {threshold})",
            f"inventory {p.inventory_status}",
            f"storefront {p.storefront_status}",
        ]
        if retail:
            seg.append(f"retail {retail}")
        if last_price:
            seg.append(f"supplier price {last_price}")
        if sup_txt:
            seg.append(f"supplier(s) {sup_txt}")
        line = " · ".join(seg)
        spec_txt = _specs(specs)
        if spec_txt:
            line += f"\n    specs → {spec_txt}"
        if desc:
            line += f"\n    description → {desc}"
        lines.append(line)

    # Suppliers (fetch once → reuse for the detail block AND the id→name map below).
    sup_all = (await session.execute(select(Supplier).where(Supplier.tenant_id == tenant_id).limit(200))).scalars().all()
    sup_name = {s.supplier_id: s.name for s in sup_all}
    sup_active = sum(1 for s in sup_all if (s.relationship or "active") == "active")
    sup_prospect = sum(1 for s in sup_all if s.relationship == "prospect")

    pos = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id).limit(120))).scalars().all()
    po_sup = {po.po_id: sup_name.get(po.supplier_id, po.supplier_id[:8]) for po in pos}
    po_total = sum(float(po.total_amount or 0) for po in pos)
    po_pending = sum(1 for po in pos if po.status == "pending_hitl")
    ships = (await session.execute(select(Shipment).where(Shipment.tenant_id == tenant_id).limit(120))).scalars().all()
    ship_intransit = sum(1 for sh in ships if sh.status != "arrived")

    detail_blocks: list[str] = ["=== PRODUCTS (full detail) ===\n" + "\n".join(lines)]
    extras: list[str] = []

    if sup_all:
        detail_blocks.append("=== SUPPLIERS ===\n" + "\n".join(
            f"- {s.name} ({s.relationship or 'active'})"
            f"{' · ' + s.category if s.category else ''}"
            f"{' · MOQ ' + str(s.moq) if s.moq else ''}"
            f"{' · rating ' + str(s.rating) if s.rating is not None else ''}"
            f"{' · score ' + str(s.score) if s.score is not None else ''}"
            f"{' · ' + s.email if s.email else ''}"
            f"{' · ' + s.phone if s.phone else ''}"
            f"{' · ' + s.location if s.location else ''}"
            f"{' · ' + (s.currency or '') if s.currency else ''}"
            f"{' · web ' + s.website if s.website else ''}"
            f"{' · offers ' + s.offering if s.offering else ''}"
            for s in sup_all
        ))

    if pos:
        detail_blocks.append("=== PURCHASE ORDERS ===\n" + "\n".join(
            f"- {po.po_number} → {po_sup.get(po.po_id, po.supplier_id[:8])} · status {po.status}"
            f"{' · total ' + _money(po.total_amount, po.currency) if po.total_amount is not None else ''}"
            f"{' · delivery ' + str(po.requested_delivery_date) if po.requested_delivery_date else ''}"
            f" · {len(po.line_items or [])} line(s)"
            for po in pos
        ))

    if ships:
        detail_blocks.append("=== SHIPMENTS & TRACKING ===\n" + "\n".join(
            f"- {po_sup.get(sh.po_id, 'PO ' + sh.po_id[:10])} · status {sh.status}"
            f"{' · carrier ' + sh.carrier if sh.carrier else ''}"
            f"{' · tracking ' + sh.tracking_number if sh.tracking_number else ''}"
            f"{' · ETA ' + str(sh.expected_arrival_date) if sh.expected_arrival_date else ''}"
            f"{' (' + sh.expected_arrival_at.isoformat() + ')' if sh.expected_arrival_at else ''}"
            f"{' · received ' + sh.received_at.isoformat() if sh.received_at else ''}"
            for sh in ships
        ))

    # HITL approvals awaiting the user.
    with contextlib.suppress(Exception):
        from app.infra.db.models.hitl import HITLAction  # noqa: PLC0415

        hitl_rows = (await session.execute(select(HITLAction).where(HITLAction.tenant_id == tenant_id, HITLAction.status == "pending").limit(60))).scalars().all()
        extras.append(f"HITL approvals pending: {len(hitl_rows)}" + (
            " (" + ", ".join(sorted({h.action_type.replace('_', ' ') for h in hitl_rows})) + ")" if hitl_rows else ""
        ))
        if hitl_rows:
            detail_blocks.append("=== PENDING APPROVALS (HITL) ===\n" + "\n".join(
                f"- {h.action_type.replace('_', ' ')} · "
                f"{str((h.payload or {}).get('subject') or (h.payload or {}).get('to') or (h.payload or {}).get('supplier_name') or '').strip()[:120]}"
                for h in hitl_rows
            ))

    # Dunning + invoices (receivables / payables).
    with contextlib.suppress(Exception):
        from app.infra.db.models.dunning import DunningSequence, Invoice  # noqa: PLC0415

        dun = (await session.execute(select(func.count()).select_from(DunningSequence).where(DunningSequence.tenant_id == tenant_id, DunningSequence.status == "active"))).scalar_one()
        inv_rows = (await session.execute(select(Invoice).where(Invoice.tenant_id == tenant_id).limit(120))).scalars().all()
        unpaid = [i for i in inv_rows if i.status != "paid"]
        extras.append(f"Dunning sequences active: {int(dun)}. Unpaid invoices: {len(unpaid)} (total {sum(float(i.amount_due or 0) for i in unpaid):.2f}).")
        if inv_rows:
            detail_blocks.append("=== INVOICES ===\n" + "\n".join(
                f"- {i.invoice_id[:10]} · status {i.status}"
                f"{' · due ' + _money(i.amount_due, i.currency) if i.amount_due is not None else ''}"
                for i in inv_rows
            ))

    # Recent activity feed (last events) — the running log of "what just happened".
    with contextlib.suppress(Exception):
        from app.infra.db.models.notification import Notification  # noqa: PLC0415

        notes = (await session.execute(select(Notification).where(Notification.tenant_id == tenant_id).order_by(Notification.created_at.desc()).limit(20))).scalars().all()
        if notes:
            detail_blocks.append("=== RECENT ACTIVITY ===\n" + "\n".join(f"- {n.title}: {n.body or ''}".strip() for n in notes))

    cat_txt = ", ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda x: -x[1])[:14]) or "none"
    summary = (
        f"Products: {len(prods)} ({enriched} enriched; total units in stock {total_stock}; {low} low-stock; {published} published to storefront).\n"
        f"Product categories/types: {cat_txt}.\n"
        f"Suppliers: {sup_active} active (we do business with), {sup_prospect} prospects.\n"
        f"Purchase orders: {len(pos)} total, {po_pending} awaiting approval, total spend {po_total:.2f}.\n"
        f"Shipments in transit: {ship_intransit}.\n"
        + "\n".join(extras)
    )
    return summary, "\n\n".join(detail_blocks)


class ChatMessage(StrictModel):
    role: str  # user | assistant
    content: str


class AssistantRequest(StrictModel):
    role: str = "advisor"  # advisor | command_center
    message: str
    history: list[ChatMessage] = []
    lang: str = "en"


class AssistantResponse(StrictModel):
    answer: str
    role: str


@router.post("/chat", response_model=AssistantResponse, summary="Chat with the AI Assistant (advisor or command-center role)")
async def chat(
    body: AssistantRequest, current_user: CurrentUser, session: SessionDep
) -> AssistantResponse:
    summary, detail = await _snapshot(session, current_user.tenant_id)
    lang_name = _LANG.get(body.lang, "English")

    if body.role == "command_center":
        system = (
            "You are the Command-Center assistant for an import/distribution business on the "
            "Mawrid platform. Answer the user's question using ONLY the live data below — be "
            "factual and exact (counts, quantities, totals, dates, names). The data is the COMPLETE "
            "current state: every product with its FULL description and ALL specifications "
            "(dimensions, capacity, colour, weight, material, etc.), every supplier (relationship, "
            "MOQ, email, phone, location, rating, website), every purchase order, every shipment "
            "with carrier/tracking/ETA, pending approvals, invoices/dunning and recent activity. "
            "For a specific product, read its 'specs →' and 'description →' lines. If they ask "
            "'how many X', count matching items. Only say something is unavailable if it is truly "
            f"absent from the data below. Reply in {lang_name}.\n\n"
            f"=== LIVE DATA SNAPSHOT ===\n{summary}\n\n{detail}"
        )
    else:
        system = (
            "You are a senior operations & finance advisor for a Lebanon/MENA importer-distributor, "
            "embedded in the Mawrid platform. You think like a seasoned consultant, not a generic "
            "chatbot. When a question is relevant, reason across these levers: cash flow & working "
            "capital; supplier reliability & concentration risk; inventory turns & dead stock; "
            "pricing & margin; dunning & collections; procurement timing vs supplier lead times.\n\n"
            "ALWAYS answer in this shape:\n"
            "1) **Recommendation** — one decisive sentence.\n"
            "2) **Steps** — 2-4 concrete, ordered actions the importer can take this week.\n"
            "3) **Why** — a short rationale grounded in the live numbers below.\n\n"
            "Cite the tenant's REAL figures from the snapshot (counts, totals, low-stock, pending "
            "approvals, shipments, dunning). Never invent numbers; if the data lacks something, say so "
            "and state the assumption. Be specific and tight — no filler, no generic platitudes. "
            f"Reply in {lang_name}.\n\n"
            f"=== LIVE SNAPSHOT ===\n{summary}"
        )

    messages: list[dict[str, object]] = [{"role": "system", "content": system}]
    for m in body.history[-8:]:
        messages.append({"role": "assistant" if m.role == "assistant" else "user", "content": m.content})
    messages.append({"role": "user", "content": body.message})

    answer = await chat_completion(messages=messages, temperature=0.3, max_tokens=700)
    return AssistantResponse(answer=answer.strip(), role=body.role)
