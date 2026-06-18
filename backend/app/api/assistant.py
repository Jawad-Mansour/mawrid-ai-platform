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
    """Return (summary, product_lines). summary = high-level counts; product_lines = a
    compact per-product list so the command-center role can answer counting questions."""
    prods = (
        await session.execute(select(Product).where(Product.tenant_id == tenant_id).limit(200))
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
        lines.append(f"- {p.product_name} (stock {p.qty_in_stock}, storefront {p.storefront_qty}){price}")

    sup_active = (await session.execute(select(func.count()).select_from(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.relationship == "active"))).scalar_one()
    sup_prospect = (await session.execute(select(func.count()).select_from(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.relationship == "prospect"))).scalar_one()
    po_stat = (await session.execute(select(func.count(), func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).where(PurchaseOrder.tenant_id == tenant_id))).one()
    po_pending = (await session.execute(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status == "pending_hitl"))).scalar_one()
    ship_intransit = (await session.execute(select(func.count()).select_from(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.status != "arrived"))).scalar_one()

    cat_txt = ", ".join(f"{k}: {v}" for k, v in sorted(cats.items(), key=lambda x: -x[1])[:12]) or "none"
    summary = (
        f"Products: {len(prods)} (total units in stock {total_stock}; {low} low-stock; {published} published to storefront).\n"
        f"Product categories/types: {cat_txt}.\n"
        f"Suppliers: {sup_active} active (we do business with), {sup_prospect} prospects.\n"
        f"Purchase orders: {int(po_stat[0])} total, {po_pending} awaiting approval, total spend {float(po_stat[1] or 0):.2f}.\n"
        f"Shipments in transit: {ship_intransit}."
    )
    return summary, "\n".join(lines[:200])


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
    summary, product_lines = await _snapshot(session, current_user.tenant_id)
    lang_name = _LANG.get(body.lang, "English")

    if body.role == "command_center":
        system = (
            "You are the Command-Center assistant for an import/distribution business on the "
            "Mawrid platform. Answer the user's question using ONLY the live data below — be "
            "factual and exact (counts, quantities, totals). If they ask 'how many X', count "
            f"matching products from the list. If the data doesn't contain it, say so. Reply in {lang_name}.\n\n"
            f"=== LIVE DATA SNAPSHOT ===\n{summary}\n\n=== PRODUCTS ===\n{product_lines}"
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
