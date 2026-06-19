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


async def _snapshot(session: Any, tenant_id: str) -> tuple[str, str]:
    """Return (summary, detail). summary = a complete situational brief across catalog,
    procurement, suppliers, inventory, shipments, dunning, HITL and recent activity;
    detail = per-product + per-supplier + per-shipment lines so the command-center role
    can answer ANY factual question (counts, dates, totals, who/what/when)."""
    prods = (
        await session.execute(select(Product).where(Product.tenant_id == tenant_id).limit(300))
    ).scalars().all()
    cats: dict[str, int] = {}
    total_stock = 0
    low = 0
    published = 0
    lines: list[str] = []
    for p in prods:
        specs = p.specifications or {}
        cat = str(specs.get("Type") or specs.get("Category") or specs.get("Brand") or "other")
        cats[cat] = cats.get(cat, 0) + 1
        total_stock += p.qty_in_stock
        if p.qty_in_stock <= (p.reorder_threshold if p.reorder_threshold is not None else 5):
            low += 1
        if p.storefront_status == "published":
            published += 1
        price = ""
        hist = p.price_history or []
        if hist and isinstance(hist[-1], dict) and hist[-1].get("price") is not None:
            with contextlib.suppress(TypeError, ValueError):
                price = f" @ {float(hist[-1]['price'])} {p.currency or 'USD'}"
        desc = (p.description or "").replace("\n", " ").strip()[:140]
        lines.append(
            f"- {p.product_name} [{p.sku or '—'}] · type {cat} · stock {p.qty_in_stock} "
            f"(storefront {p.storefront_qty}, status {p.storefront_status}){price}"
            f"{' — ' + desc if desc else ''}"
        )

    sup_active = (await session.execute(select(func.count()).select_from(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.relationship == "active"))).scalar_one()
    sup_prospect = (await session.execute(select(func.count()).select_from(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.relationship == "prospect"))).scalar_one()
    po_stat = (await session.execute(select(func.count(), func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(PurchaseOrder.tenant_id == tenant_id))).one()
    po_pending = (await session.execute(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status == "pending_hitl"))).scalar_one()
    ship_intransit = (await session.execute(select(func.count()).select_from(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.status != "arrived"))).scalar_one()

    detail_blocks: list[str] = ["=== PRODUCTS ===\n" + "\n".join(lines[:300])]
    extras: list[str] = []

    # Suppliers (names, relationship, MOQ, email) — for "which supplier / their MOQ" questions.
    with contextlib.suppress(Exception):
        sup_rows = (await session.execute(select(Supplier).where(Supplier.tenant_id == tenant_id).limit(80))).scalars().all()
        if sup_rows:
            detail_blocks.append("=== SUPPLIERS ===\n" + "\n".join(
                f"- {s.name} ({s.relationship or 'active'})"
                f"{' · MOQ ' + str(s.moq) if s.moq else ''}"
                f"{' · ' + s.email if s.email else ''}"
                f"{' · ' + s.location if s.location else ''}" for s in sup_rows
            ))

    # Shipments with ETA + status.
    with contextlib.suppress(Exception):
        ships = (await session.execute(select(Shipment).where(Shipment.tenant_id == tenant_id).limit(60))).scalars().all()
        if ships:
            detail_blocks.append("=== SHIPMENTS ===\n" + "\n".join(
                f"- PO {sh.po_id[:10]} · status {sh.status}"
                f"{' · ETA ' + str(sh.expected_arrival_date) if sh.expected_arrival_date else ''}" for sh in ships
            ))

    # HITL approvals awaiting the user.
    with contextlib.suppress(Exception):
        from app.infra.db.models.hitl import HITLAction  # noqa: PLC0415

        hitl_rows = (await session.execute(select(HITLAction).where(HITLAction.tenant_id == tenant_id, HITLAction.status == "pending").limit(40))).scalars().all()
        extras.append(f"HITL approvals pending: {len(hitl_rows)}" + (
            " (" + ", ".join(sorted({h.action_type.replace('_', ' ') for h in hitl_rows})) + ")" if hitl_rows else ""
        ))

    # Dunning + invoices (receivables / payables).
    with contextlib.suppress(Exception):
        from app.infra.db.models.dunning import DunningSequence, Invoice  # noqa: PLC0415

        dun = (await session.execute(select(func.count()).select_from(DunningSequence).where(DunningSequence.tenant_id == tenant_id, DunningSequence.status == "active"))).scalar_one()
        inv = (await session.execute(select(func.count(), func.coalesce(func.sum(Invoice.amount_due), 0)).where(Invoice.tenant_id == tenant_id, Invoice.status != "paid"))).one()
        extras.append(f"Dunning sequences active: {int(dun)}. Unpaid invoices: {int(inv[0])} (total {float(inv[1] or 0):.2f}).")

    # Recent activity feed (last events).
    with contextlib.suppress(Exception):
        from app.infra.db.models.notification import Notification  # noqa: PLC0415

        notes = (await session.execute(select(Notification).where(Notification.tenant_id == tenant_id).order_by(Notification.created_at.desc()).limit(12))).scalars().all()
        if notes:
            detail_blocks.append("=== RECENT ACTIVITY ===\n" + "\n".join(f"- {n.title}: {n.body or ''}".strip() for n in notes))

    cat_txt = ", ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda x: -x[1])[:14]) or "none"
    summary = (
        f"Products: {len(prods)} (total units in stock {total_stock}; {low} low-stock; {published} published to storefront).\n"
        f"Product categories/types: {cat_txt}.\n"
        f"Suppliers: {sup_active} active (we do business with), {sup_prospect} prospects.\n"
        f"Purchase orders: {int(po_stat[0])} total, {po_pending} awaiting approval, total spend {float(po_stat[1] or 0):.2f}.\n"
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
            "factual and exact (counts, quantities, totals, dates, names). You can answer about "
            "products, stock, suppliers (and their MOQ/email), purchase orders, shipments & ETAs, "
            "HITL approvals, dunning/invoices and recent activity. If they ask 'how many X', count "
            f"matching items. If the data doesn't contain it, say so plainly. Reply in {lang_name}.\n\n"
            f"=== LIVE DATA SNAPSHOT ===\n{summary}\n\n{detail}"
        )
    else:
        system = (
            "You are the Business Advisor for an import/distribution business on Mawrid. Give "
            "concrete, practical financial & business advice — what to do, how to improve, how to "
            "handle a specific supplier/customer/decision. Use the live snapshot for context and be "
            f"specific to their situation. Concise and actionable. Reply in {lang_name}.\n\n"
            f"=== LIVE SNAPSHOT ===\n{summary}"
        )

    messages: list[dict[str, object]] = [{"role": "system", "content": system}]
    for m in body.history[-8:]:
        messages.append({"role": "assistant" if m.role == "assistant" else "user", "content": m.content})
    messages.append({"role": "user", "content": body.message})

    answer = await chat_completion(messages=messages, temperature=0.3, max_tokens=700)
    return AssistantResponse(answer=answer.strip(), role=body.role)
