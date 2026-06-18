"""
Feature:  Order Management & Procurement
Layer:    API / Router
Module:   app.api.procurement
Purpose:  HTTP routes for order draft CRUD, "Submit Draft" (lock), "Place Order"
          (GPT-4o PO text → purchase_order_send HITL action), shipment tracking,
          goods receiving (atomic stock update: qty_in_stock += received - damaged),
          storefront publishing (retail price + qty). Triggers n8n WF-04, WF-05, WF-06.
Depends:  app.core.procurement.services, app.core.hitl.services, app.api.deps,
          app.infra.db.repos.*, app.infra.llm.openai
HITL:     purchase_order_send, dispute_letter
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, date, datetime
from typing import Any

import structlog
import yaml
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, update

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.models.product import Product
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.db.repos.order_repo import OrderRepository
from app.infra.db.repos.shipment_repo import ShipmentRepository
from app.infra.db.repos.supplier_repo import SupplierRepository
from app.infra.llm.openai import chat_completion

# Loaded lazily inside dispute endpoint to avoid circular imports at module load
_dispute_prompt_cache: dict[str, Any] = {}

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/procurement", tags=["procurement"])


# ── Helpers ────────────────────────────────────────────────────────────────────


def _load_prompt(template_name: str) -> dict[str, str]:
    import pathlib

    prompts_dir = pathlib.Path(__file__).parent.parent.parent / "prompts" / "communication"
    path = prompts_dir / f"{template_name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


async def _draft_po_text(
    supplier_name: str,
    tenant_name: str,
    po_number: str,
    line_items: list[dict[str, Any]],
    delivery_date: str | None,
    language: str,
    notes: str | None,
) -> str:
    """Generate PO document text via GPT-4o using purchase_order.yaml template."""
    items_summary = ", ".join(
        f"{int(it.get('quantity', 0))}× {it.get('product_name', '')}"
        f" ({it.get('sku') or 'no code'})"
        for it in line_items
    )
    try:
        prompt_data = _load_prompt("purchase_order")
        system_prompt = prompt_data.get("system", "You are a procurement specialist.").format(
            language=language
        )
        user_prompt = prompt_data.get("draft_po", "").format(
            supplier_name=supplier_name,
            supplier_address="",
            tenant_name=tenant_name,
            po_number=po_number,
            date=date.today().isoformat(),
            line_items_json=items_summary or str(line_items),
            payment_terms="NET 30",
            delivery_address=delivery_date or "at your earliest convenience",
            notes=notes or "",
        )
    except Exception:
        system_prompt = (
            f"You are a procurement officer writing a formal purchase-request email "
            f"to a supplier. Language: {language}."
        )
        user_prompt = (
            f"Write a short, formal email to {supplier_name} opening with "
            f"'Dear {supplier_name},' requesting to place purchase order {po_number}. "
            f"Items: {items_summary}. Say the full codes & quantities are in the attached "
            f"spreadsheet and ask them to confirm availability, prices and lead time. "
            f"Sign off as {tenant_name}. Output only the email body."
        )

    text = await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    import re  # noqa: PLC0415

    # Strip any markdown code fences the model may wrap the letter in.
    body = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip()).strip()
    # Guarantee a formal salutation addressing the company, even if the model omits it.
    if not re.match(r"^\s*(dear|hello|hi|to whom|bonjour|cher|عزيز|السلام)", body, re.IGNORECASE):
        body = f"Dear {supplier_name},\n\n{body}"
    return body


# ── Order Drafts ───────────────────────────────────────────────────────────────


class DraftLineItem(StrictModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    currency: str = "USD"
    sku: str | None = None


_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _order_excel(
    line_items: list[dict[str, Any]], supplier_name: str, po_number: str, currency: str
) -> bytes:
    """Build the order request spreadsheet (codes · quantities · sum)."""
    from io import BytesIO  # noqa: PLC0415

    from openpyxl import Workbook  # noqa: PLC0415

    wb = Workbook()
    ws = wb.active
    ws.title = "Order"
    ws.append([f"Purchase Order {po_number}"])
    ws.append([f"Supplier: {supplier_name}"])
    ws.append([])
    ws.append(["Code", "Product", "Quantity", "Unit Price", "Line Total"])
    total = 0.0
    for it in line_items:
        qty = int(it.get("quantity", 0))
        unit = float(it.get("unit_price", 0) or 0)
        line_total = round(qty * unit, 2)
        total += line_total
        ws.append([
            str(it.get("sku") or it.get("product_id", "")),
            str(it.get("product_name", "")),
            qty,
            unit,
            line_total,
        ])
    ws.append([])
    ws.append(["", "", "", f"TOTAL ({currency})", round(total, 2)])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


class CreateDraftRequest(StrictModel):
    supplier_id: str
    line_items: list[DraftLineItem]
    notes: str | None = None
    desired_delivery_date: str | None = None


class OrderDraftResponse(StrictModel):
    order_id: str
    supplier_id: str
    status: str
    line_items: list[Any]
    notes: str | None
    desired_delivery_date: str | None
    created_at: str


class UpdateDraftRequest(StrictModel):
    line_items: list[DraftLineItem] | None = None
    notes: str | None = None
    desired_delivery_date: str | None = None


@router.post(
    "/orders/draft",
    response_model=OrderDraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an order draft for a supplier",
)
async def create_order_draft(
    body: CreateDraftRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> OrderDraftResponse:
    supplier_repo = SupplierRepository(session, current_user.tenant_id)
    supplier = await supplier_repo.get_by_id(body.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    order_repo = OrderRepository(session, current_user.tenant_id)
    items = [item.model_dump() for item in body.line_items]
    draft = await order_repo.create_draft(
        order_id=uuid.uuid4().hex,
        supplier_id=body.supplier_id,
        line_items=items,
        notes=body.notes,
        desired_delivery_date=body.desired_delivery_date,
    )
    await session.commit()
    return OrderDraftResponse(
        order_id=draft.order_id,
        supplier_id=draft.supplier_id,
        status=draft.status,
        line_items=draft.line_items,
        notes=draft.notes,
        desired_delivery_date=str(draft.desired_delivery_date)
        if draft.desired_delivery_date
        else None,
        created_at=str(draft.created_at),
    )


@router.get(
    "/orders",
    response_model=list[OrderDraftResponse],
    summary="List order drafts",
)
async def list_order_drafts(
    current_user: CurrentUser,
    session: SessionDep,
    status_filter: str | None = None,
) -> list[OrderDraftResponse]:
    order_repo = OrderRepository(session, current_user.tenant_id)
    drafts = await order_repo.list_drafts(status=status_filter)
    return [
        OrderDraftResponse(
            order_id=d.order_id,
            supplier_id=d.supplier_id,
            status=d.status,
            line_items=d.line_items,
            notes=d.notes,
            desired_delivery_date=str(d.desired_delivery_date) if d.desired_delivery_date else None,
            created_at=str(d.created_at),
        )
        for d in drafts
    ]


@router.get(
    "/orders/{order_id}",
    response_model=OrderDraftResponse,
    summary="Get order draft detail",
)
async def get_order_draft(
    order_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> OrderDraftResponse:
    order_repo = OrderRepository(session, current_user.tenant_id)
    draft = await order_repo.get_draft_by_id(order_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return OrderDraftResponse(
        order_id=draft.order_id,
        supplier_id=draft.supplier_id,
        status=draft.status,
        line_items=draft.line_items,
        notes=draft.notes,
        desired_delivery_date=str(draft.desired_delivery_date)
        if draft.desired_delivery_date
        else None,
        created_at=str(draft.created_at),
    )


@router.put(
    "/orders/{order_id}",
    response_model=OrderDraftResponse,
    summary="Update an order draft (only while in 'draft' status)",
)
async def update_order_draft(
    order_id: str,
    body: UpdateDraftRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> OrderDraftResponse:
    order_repo = OrderRepository(session, current_user.tenant_id)
    draft = await order_repo.get_draft_by_id(order_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if draft.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit a draft with status '{draft.status}'.",
        )

    items = [item.model_dump() for item in body.line_items] if body.line_items else None
    await order_repo.update_draft(
        order_id=order_id,
        line_items=items,
        notes=body.notes,
        desired_delivery_date=body.desired_delivery_date,
    )
    await session.commit()

    updated = await order_repo.get_draft_by_id(order_id)
    assert updated is not None
    return OrderDraftResponse(
        order_id=updated.order_id,
        supplier_id=updated.supplier_id,
        status=updated.status,
        line_items=updated.line_items,
        notes=updated.notes,
        desired_delivery_date=str(updated.desired_delivery_date)
        if updated.desired_delivery_date
        else None,
        created_at=str(updated.created_at),
    )


@router.get(
    "/orders/{order_id}/excel",
    summary="Download the order request spreadsheet (codes · quantities · sum)",
)
async def download_order_excel(
    order_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> Response:
    order_repo = OrderRepository(session, current_user.tenant_id)
    draft = await order_repo.get_draft_by_id(order_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    supplier_repo = SupplierRepository(session, current_user.tenant_id)
    supplier = await supplier_repo.get_by_id(draft.supplier_id)
    name = supplier.name if supplier else "Supplier"
    currency = supplier.currency if supplier else "USD"
    xlsx = _order_excel(draft.line_items or [], name, order_id[:8].upper(), currency)
    return Response(
        content=xlsx,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="order-{order_id[:8]}.xlsx"'},
    )


class OrderExcelRequest(StrictModel):
    line_items: list[DraftLineItem]
    supplier_name: str = "Supplier"
    po_number: str = "ORDER"
    currency: str = "USD"


@router.post(
    "/order-excel",
    summary="Build the order spreadsheet from the (possibly edited) line items",
)
async def build_order_excel(
    body: OrderExcelRequest,
    current_user: CurrentUser,
) -> Response:
    """Render the order Excel on demand from whatever line items the review screen
    currently shows — so edits to quantity/price are reflected in the download."""
    xlsx = _order_excel(
        [it.model_dump() for it in body.line_items],
        body.supplier_name,
        body.po_number,
        body.currency,
    )
    return Response(
        content=xlsx,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{body.po_number}.xlsx"'},
    )


@router.post(
    "/orders/{order_id}/submit",
    summary="Submit an order draft (locks it — no more edits)",
)
async def submit_order_draft(
    order_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    order_repo = OrderRepository(session, current_user.tenant_id)
    draft = await order_repo.get_draft_by_id(order_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if draft.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Draft already submitted (status: {draft.status}).",
        )

    await order_repo.set_draft_status(order_id, "submitted")
    await session.commit()
    return {"order_id": order_id, "status": "submitted"}


@router.post(
    "/orders/{order_id}/place",
    summary="Place order — drafts PO via GPT-4o, creates purchase_order_send HITL action",
)
async def place_order(
    order_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    """
    'Place Order' is separate from 'Submit Draft':
    - Submit = lock the product list (no more edits)
    - Place Order = draft the PO text and send for HITL approval
    This creates a purchase_order_send HITL action and a PurchaseOrder record.
    """
    tenant_id = current_user.tenant_id
    order_repo = OrderRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)

    draft = await order_repo.get_draft_by_id(order_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if draft.status not in ("submitted", "draft"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order status must be 'submitted' to place (current: {draft.status}).",
        )

    supplier = await supplier_repo.get_by_id(draft.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    # Placing an order means we now do business with them → active relationship.
    if getattr(supplier, "relationship", "active") != "active":
        await supplier_repo.update(draft.supplier_id, relationship="active")

    po_id = uuid.uuid4().hex
    po_number = f"PO-{datetime.now(UTC).strftime('%Y%m%d')}-{po_id[:6].upper()}"

    line_items: list[dict[str, Any]] = draft.line_items or []
    total = sum(
        int(item.get("quantity", 0)) * float(item.get("unit_price", 0)) for item in line_items
    )

    # Friendly company name for the signature (fall back to the id if missing).
    tenant_name = tenant_id
    from app.infra.db.models.tenant import Tenant  # noqa: PLC0415

    tenant_row = await session.get(Tenant, tenant_id)
    if tenant_row is not None and tenant_row.name:
        tenant_name = tenant_row.name

    po_text = await _draft_po_text(
        supplier_name=supplier.name,
        tenant_name=tenant_name,
        po_number=po_number,
        line_items=line_items,
        delivery_date=str(draft.desired_delivery_date) if draft.desired_delivery_date else None,
        language=supplier.language,
        notes=draft.notes,
    )

    # Build the order Excel (codes · quantities · sum) and attach it to the PO email.
    import base64 as _b64  # noqa: PLC0415

    xlsx_bytes = _order_excel(line_items, supplier.name, po_number, supplier.currency)
    xlsx_name = f"{po_number}.xlsx"

    hitl_action_id = uuid.uuid4().hex
    action = await hitl_repo.create(
        action_id=hitl_action_id,
        action_type="purchase_order_send",
        payload={
            "po_id": po_id,
            "po_number": po_number,
            "order_id": order_id,
            "supplier_id": draft.supplier_id,
            "supplier_name": supplier.name,
            "to": supplier.email or "",
            "subject": f"Purchase Order {po_number}",
            "body": po_text,
            "language": supplier.language,
            "line_items": line_items,
            "total": total,
            "currency": supplier.currency,
            "attachment_b64": _b64.b64encode(xlsx_bytes).decode(),
            "attachment_filename": xlsx_name,
            "attachment_mime": _XLSX_MIME,
        },
    )

    await order_repo.create_purchase_order(
        po_id=po_id,
        order_draft_id=order_id,
        supplier_id=draft.supplier_id,
        po_number=po_number,
        line_items=line_items,
        po_text=po_text,
        hitl_action_id=action.action_id,
        currency=supplier.currency,
        total_amount=total,
        requested_delivery_date=str(draft.desired_delivery_date)
        if draft.desired_delivery_date
        else None,
    )

    await order_repo.set_draft_status(order_id, "pending_hitl")

    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415

    await record_event(
        session, tenant_id, kind="order_created",
        title="Order created",
        body=f"{po_number} for {supplier.name} is drafted — review & send it.",
        link="/purchase-orders",
    )
    await session.commit()

    logger.info("purchase_order_created", po_id=po_id, hitl_action_id=hitl_action_id)
    return {
        "po_id": po_id,
        "hitl_action_id": hitl_action_id,
        "status": "pending_hitl",
        "po_number": po_number,
    }


# ── Purchase Orders ────────────────────────────────────────────────────────────


class PurchaseOrderResponse(StrictModel):
    po_id: str
    order_draft_id: str
    supplier_id: str
    po_number: str
    status: str
    total_amount: float | None
    currency: str
    created_at: str


@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderResponse],
    summary="List all purchase orders",
)
async def list_purchase_orders(
    current_user: CurrentUser,
    session: SessionDep,
) -> list[PurchaseOrderResponse]:
    order_repo = OrderRepository(session, current_user.tenant_id)
    pos = await order_repo.list_purchase_orders()
    return [
        PurchaseOrderResponse(
            po_id=p.po_id,
            order_draft_id=p.order_draft_id,
            supplier_id=p.supplier_id,
            po_number=p.po_number,
            status=p.status,
            total_amount=float(p.total_amount) if p.total_amount is not None else None,
            currency=p.currency,
            created_at=str(p.created_at),
        )
        for p in pos
    ]


# ── PO email thread (response tracking — Screen 3) ──────────────────────────────


class PODetailResponse(StrictModel):
    po_id: str
    po_number: str
    supplier_id: str
    supplier_name: str | None
    supplier_email: str | None
    status: str
    total_amount: float | None
    currency: str
    po_text: str | None
    line_items: list[Any]
    hitl_action_id: str | None
    arrival_date: str | None
    sent_at: str | None
    created_at: str
    messages: list[dict[str, Any]]


@router.get(
    "/purchase-orders/{po_id}",
    response_model=PODetailResponse,
    summary="Purchase order detail with the supplier email thread",
)
async def get_purchase_order(
    po_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> PODetailResponse:
    order_repo = OrderRepository(session, current_user.tenant_id)
    po = await order_repo.get_po_by_id(po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")
    supplier_repo = SupplierRepository(session, current_user.tenant_id)
    sup = await supplier_repo.get_by_id(po.supplier_id)
    return PODetailResponse(
        po_id=po.po_id,
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=sup.name if sup else None,
        supplier_email=sup.email if sup else None,
        status=po.status,
        total_amount=float(po.total_amount) if po.total_amount is not None else None,
        currency=po.currency,
        po_text=po.po_text,
        line_items=po.line_items or [],
        hitl_action_id=po.hitl_action_id,
        arrival_date=str(po.requested_delivery_date) if po.requested_delivery_date else None,
        sent_at=str(po.sent_at) if po.sent_at else None,
        created_at=str(po.created_at),
        messages=po.messages or [],
    )


class LogMessageRequest(StrictModel):
    body: str
    sender: str = "Supplier"
    direction: str = "inbound"


@router.post(
    "/purchase-orders/{po_id}/messages",
    summary="Log a message in the PO thread (e.g. a supplier reply received by email)",
)
async def log_po_message(
    po_id: str,
    body: LogMessageRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    order_repo = OrderRepository(session, current_user.tenant_id)
    if await order_repo.get_po_by_id(po_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")
    await order_repo.append_po_message(
        po_id,
        {
            "direction": body.direction,
            "sender": body.sender,
            "body": body.body,
            "at": datetime.now(UTC).isoformat(),
        },
    )
    if body.direction == "inbound":
        await order_repo.set_po_status(po_id, "replied")
        po = await order_repo.get_po_by_id(po_id)
        from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415

        await record_event(
            session, current_user.tenant_id, kind="supplier_reply",
            title="Supplier replied",
            body=f"A reply was logged on {po.po_number if po else 'a purchase order'}.",
            link=f"/purchase-orders/{po_id}",
        )
    await session.commit()
    return {"po_id": po_id, "status": "logged"}


class DraftReplyResponse(StrictModel):
    reply: str


@router.post(
    "/purchase-orders/{po_id}/draft-reply",
    response_model=DraftReplyResponse,
    summary="AI-draft the next reply to the supplier, based on the thread so far",
)
async def draft_po_reply(
    po_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> DraftReplyResponse:
    order_repo = OrderRepository(session, current_user.tenant_id)
    po = await order_repo.get_po_by_id(po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")
    supplier_repo = SupplierRepository(session, current_user.tenant_id)
    sup = await supplier_repo.get_by_id(po.supplier_id)
    lang = sup.language if sup else "en"
    thread = "\n\n".join(
        f"[{m.get('direction')}] {m.get('sender')}: {m.get('body')}" for m in (po.messages or [])
    )
    reply = await chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a procurement officer for the importer. Write a concise, professional "
                    f"reply to the supplier in {lang}, continuing the email thread for purchase order "
                    f"{po.po_number}. Address their latest message directly. Output only the email body."
                ),
            },
            {"role": "user", "content": f"Email thread so far:\n{thread or '(no replies yet)'}\n\nDraft our next reply."},
        ],
        temperature=0.3,
        max_tokens=700,
    )
    return DraftReplyResponse(reply=reply.strip())


class SendReplyRequest(StrictModel):
    body: str
    subject: str | None = None


@router.post(
    "/purchase-orders/{po_id}/reply",
    summary="Send a reply to the supplier and log it in the thread",
)
async def send_po_reply(
    po_id: str,
    body: SendReplyRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    order_repo = OrderRepository(session, current_user.tenant_id)
    po = await order_repo.get_po_by_id(po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")
    supplier_repo = SupplierRepository(session, current_user.tenant_id)
    sup = await supplier_repo.get_by_id(po.supplier_id)
    if sup is None or not sup.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supplier has no email on file.",
        )

    from app.infra.email.sender import send_email  # noqa: PLC0415

    await send_email(
        to=sup.email,
        subject=body.subject or f"Re: Purchase Order {po.po_number}",
        body=body.body,
    )
    await order_repo.append_po_message(
        po_id,
        {
            "direction": "outbound",
            "sender": "You",
            "body": body.body,
            "at": datetime.now(UTC).isoformat(),
        },
    )
    await session.commit()
    logger.info("po_reply_sent", po_id=po_id)
    return {"po_id": po_id, "status": "sent"}


class UpdatePORequest(StrictModel):
    line_items: list[DraftLineItem] | None = None
    agreed_delivery_date: str | None = None
    status: str | None = None  # e.g. "confirmed", "cancelled"
    note: str | None = None


@router.patch(
    "/purchase-orders/{po_id}",
    response_model=PODetailResponse,
    summary="Act on a PO after a supplier reply — adjust items, confirm ETA, set status",
)
async def update_purchase_order(
    po_id: str,
    body: UpdatePORequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> PODetailResponse:
    """After a supplier replies, the importer can revise the order: change or remove
    line items (total recomputed), confirm an agreed delivery/container date, or set
    the status (e.g. confirmed). Every change is logged to the thread."""
    order_repo = OrderRepository(session, current_user.tenant_id)
    po = await order_repo.get_po_by_id(po_id)
    if po is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found.")

    changes: list[str] = []
    if body.line_items is not None:
        lines = [it.model_dump() for it in body.line_items]
        po.line_items = lines
        po.total_amount = sum(
            int(it.get("quantity", 0) or 0) * float(it.get("unit_price", 0) or 0) for it in lines
        )
        changes.append(f"items updated ({len(lines)} line(s), new total {po.total_amount} {po.currency})")
    if body.agreed_delivery_date:
        import contextlib  # noqa: PLC0415

        with contextlib.suppress(ValueError):
            po.requested_delivery_date = date.fromisoformat(body.agreed_delivery_date[:10])  # type: ignore[assignment]
        changes.append(f"delivery/container date confirmed for {body.agreed_delivery_date}")
    if body.status:
        po.status = body.status
        changes.append(f"status set to {body.status}")

    summary = body.note or ("; ".join(changes) if changes else "order reviewed")
    await order_repo.append_po_message(
        po_id,
        {
            "direction": "system",
            "sender": "You",
            "body": f"Order updated: {summary}.",
            "at": datetime.now(UTC).isoformat(),
        },
    )
    await session.commit()

    sup = await SupplierRepository(session, current_user.tenant_id).get_by_id(po.supplier_id)
    logger.info("po_updated", po_id=po_id, changes=changes)
    return PODetailResponse(
        po_id=po.po_id,
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=sup.name if sup else None,
        supplier_email=sup.email if sup else None,
        status=po.status,
        total_amount=float(po.total_amount) if po.total_amount is not None else None,
        currency=po.currency,
        po_text=po.po_text,
        line_items=po.line_items or [],
        hitl_action_id=po.hitl_action_id,
        arrival_date=str(po.requested_delivery_date) if po.requested_delivery_date else None,
        sent_at=str(po.sent_at) if po.sent_at else None,
        created_at=str(po.created_at),
        messages=po.messages or [],
    )


# ── Shipments ──────────────────────────────────────────────────────────────────


class CreateShipmentRequest(StrictModel):
    po_id: str
    carrier: str | None = None
    tracking_number: str | None = None
    expected_arrival_date: str | None = None


class ShipmentResponse(StrictModel):
    shipment_id: str
    po_id: str
    carrier: str | None
    tracking_number: str | None
    expected_arrival_date: str | None
    status: str
    created_at: str


@router.post(
    "/shipments",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shipment linked to a purchase order",
)
async def create_shipment(
    body: CreateShipmentRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ShipmentResponse:
    shipment_repo = ShipmentRepository(session, current_user.tenant_id)
    shipment = await shipment_repo.create(
        shipment_id=uuid.uuid4().hex,
        po_id=body.po_id,
        carrier=body.carrier,
        tracking_number=body.tracking_number,
        expected_arrival_date=body.expected_arrival_date,
    )
    await session.commit()
    return ShipmentResponse(
        shipment_id=shipment.shipment_id,
        po_id=shipment.po_id,
        carrier=shipment.carrier,
        tracking_number=shipment.tracking_number,
        expected_arrival_date=str(shipment.expected_arrival_date)
        if shipment.expected_arrival_date
        else None,
        status=shipment.status,
        created_at=str(shipment.created_at),
    )


@router.get(
    "/shipments",
    response_model=list[ShipmentResponse],
    summary="List all shipments",
)
async def list_shipments(
    current_user: CurrentUser,
    session: SessionDep,
    status_filter: str | None = None,
) -> list[ShipmentResponse]:
    shipment_repo = ShipmentRepository(session, current_user.tenant_id)
    shipments = await shipment_repo.list_all(status=status_filter)
    return [
        ShipmentResponse(
            shipment_id=s.shipment_id,
            po_id=s.po_id,
            carrier=s.carrier,
            tracking_number=s.tracking_number,
            expected_arrival_date=str(s.expected_arrival_date) if s.expected_arrival_date else None,
            status=s.status,
            created_at=str(s.created_at),
        )
        for s in shipments
    ]


class UpdateShipmentStatusRequest(StrictModel):
    status: str
    expected_arrival_date: str | None = None


@router.put(
    "/shipments/{shipment_id}/status",
    summary="Update shipment status milestone",
)
async def update_shipment_status(
    shipment_id: str,
    body: UpdateShipmentStatusRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    valid_statuses = {"pending_shipment", "shipped", "in_transit", "at_customs", "arrived"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )
    shipment_repo = ShipmentRepository(session, current_user.tenant_id)
    shipment = await shipment_repo.get_by_id(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

    await shipment_repo.set_status(shipment_id, body.status)
    if body.expected_arrival_date:
        await shipment_repo.update_arrival_date(shipment_id, body.expected_arrival_date)
    await session.commit()
    return {"shipment_id": shipment_id, "status": body.status}


# ── Goods Received ─────────────────────────────────────────────────────────────


class ReceivedItemInput(StrictModel):
    product_id: str
    qty_received: int
    qty_damaged: int = 0


class ReceiveGoodsRequest(StrictModel):
    items: list[ReceivedItemInput]
    notes: str | None = None


class ReceiveGoodsResponse(StrictModel):
    receiving_id: str
    shipment_id: str
    status: str
    discrepancy_detected: bool
    damage_detected: bool
    stock_updates: dict[str, int]


@router.post(
    "/shipments/{shipment_id}/receive",
    response_model=ReceiveGoodsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record goods received for a shipment (atomic stock update)",
)
async def receive_goods(
    shipment_id: str,
    body: ReceiveGoodsRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ReceiveGoodsResponse:

    from app.core.procurement.services import ReceiveItem, make_goods_received_result

    tenant_id = current_user.tenant_id
    shipment_repo = ShipmentRepository(session, tenant_id)

    shipment = await shipment_repo.get_by_id(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

    # Idempotency: reject duplicate receiving
    existing = await shipment_repo.get_receiving(shipment_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Goods already received for this shipment.",
        )

    # Look up ordered quantities from PO
    order_repo = OrderRepository(session, tenant_id)
    pos = await order_repo.list_purchase_orders()
    ordered_items: list[dict[str, Any]] = []
    for po in pos:
        if po.po_id == shipment.po_id:
            ordered_items = po.line_items or []
            break

    received = [
        ReceiveItem(
            product_id=item.product_id,
            qty_received=item.qty_received,
            qty_damaged=item.qty_damaged,
        )
        for item in body.items
    ]

    result = make_goods_received_result(
        receiving_id=uuid.uuid4().hex,
        shipment_id=shipment_id,
        ordered_items=ordered_items,
        received_items=received,
    )

    # Atomic stock update for each product
    stock_updates: dict[str, int] = {}
    for item in received:
        net_qty = max(0, item.qty_received - item.qty_damaged)
        if net_qty > 0:
            await session.execute(
                update(Product)
                .where(
                    Product.tenant_id == tenant_id,
                    Product.product_id == item.product_id,
                )
                .values(
                    qty_in_stock=Product.qty_in_stock + net_qty,
                    inventory_status="in_stock",
                )
            )
        stock_updates[item.product_id] = net_qty

    await shipment_repo.create_receiving(
        receiving_id=result.receiving_id,
        shipment_id=shipment_id,
        line_items=[item.model_dump() for item in body.items],
        received_by=current_user.user_id,
        notes=body.notes,
    )
    await shipment_repo.set_status(shipment_id, "arrived")

    # Record supplier performance events — feed Phase 7 scoring
    if shipment.po_id:
        po_list = await order_repo.list_purchase_orders()
        supplier_id_for_po: str | None = next(
            (p.supplier_id for p in po_list if p.po_id == shipment.po_id), None
        )
        if supplier_id_for_po:
            supplier_repo = SupplierRepository(session, tenant_id)
            if result.discrepancy_detected:
                await supplier_repo.increment_discrepancy(supplier_id_for_po)
            if result.damage_detected:
                await supplier_repo.increment_damage(supplier_id_for_po)

    await session.commit()

    return ReceiveGoodsResponse(
        receiving_id=result.receiving_id,
        shipment_id=shipment_id,
        status="in_stock",
        discrepancy_detected=result.discrepancy_detected,
        damage_detected=result.damage_detected,
        stock_updates=stock_updates,
    )


# ── Goods-Received report + Stock / Restock (Inventory) ─────────────────────────


async def _build_receipt(session: Any, tenant_id: str, shipment: Any) -> Any:
    """Assemble a ReceiptData from a shipment → its PO (ordered) + receiving record."""
    from app.infra.documents.receipt_pdf import ReceiptData, ReceiptLine  # noqa: PLC0415

    order_repo = OrderRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)
    shipment_repo = ShipmentRepository(session, tenant_id)

    po = await order_repo.get_po_by_id(shipment.po_id) if shipment.po_id else None
    ordered = {str(li.get("product_id")): li for li in (po.line_items if po else []) or []}
    receiving = await shipment_repo.get_receiving(shipment.shipment_id)
    received_map = {str(it.get("product_id")): it for it in (receiving.line_items if receiving else []) or []}
    sup = await supplier_repo.get_by_id(po.supplier_id) if po else None

    tenant_name = tenant_id
    from app.infra.db.models.tenant import Tenant  # noqa: PLC0415

    tr = await session.get(Tenant, tenant_id)
    if tr and tr.name:
        tenant_name = tr.name

    lines: list[Any] = []
    for pid, oli in ordered.items():
        rec = received_map.get(pid, {})
        lines.append(ReceiptLine(
            product_name=str(oli.get("product_name", "")), sku=str(oli.get("sku") or ""),
            ordered=int(oli.get("quantity", 0) or 0),
            received=int(rec.get("qty_received", 0) or 0), damaged=int(rec.get("qty_damaged", 0) or 0),
        ))
    return ReceiptData(
        po_number=po.po_number if po else shipment.shipment_id[:8].upper(),
        supplier_name=sup.name if sup else "Supplier", tenant_name=tenant_name,
        received_on=date.today(), carrier=shipment.carrier or "", container=shipment.tracking_number or "",
        lines=lines, notes=(receiving.notes if receiving else "") or "",
    ), (sup, po)


@router.get("/shipments/{shipment_id}/receipt-pdf", summary="Download the goods-received report PDF")
async def shipment_receipt_pdf(
    shipment_id: str, current_user: CurrentUser, session: SessionDep
) -> Response:
    from app.infra.documents.receipt_pdf import generate_receipt_pdf  # noqa: PLC0415

    shipment_repo = ShipmentRepository(session, current_user.tenant_id)
    shipment = await shipment_repo.get_by_id(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    data, _ = await _build_receipt(session, current_user.tenant_id, shipment)
    pdf = generate_receipt_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="receipt-{data.po_number}.pdf"'})


@router.post("/shipments/{shipment_id}/receipt-email", summary="Email the goods-received report to the supplier")
async def shipment_receipt_email(
    shipment_id: str, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    from app.infra.documents.receipt_pdf import generate_receipt_pdf  # noqa: PLC0415
    from app.infra.email.sender import send_email  # noqa: PLC0415

    shipment_repo = ShipmentRepository(session, current_user.tenant_id)
    shipment = await shipment_repo.get_by_id(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")
    data, (sup, po) = await _build_receipt(session, current_user.tenant_id, shipment)
    if sup is None or not sup.email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Supplier has no email on file.")
    pdf = generate_receipt_pdf(data)
    good = data.all_good
    subject = f"Goods received — {data.po_number}" + ("" if good else " (discrepancies noted)")
    body = (
        f"Dear {sup.name},\n\nWe have received the goods for {data.po_number}. "
        + ("Everything arrived in full and in good condition — thank you for the smooth delivery.\n\n"
           if good else
           "We found some discrepancies/damage (detailed in the attached report) and may follow up with a formal claim.\n\n")
        + f"Please find the goods-received report attached.\n\nBest regards,\n{data.tenant_name}"
    )
    await send_email(to=sup.email, subject=subject, body=body, attachment_bytes=pdf,
                     attachment_filename=f"receipt-{data.po_number}.pdf", attachment_mime="application/pdf")
    from app.infra.db.repos.notification_repo import record_event  # noqa: PLC0415

    await record_event(session, current_user.tenant_id, kind="receipt_sent",
                       title="Goods-received report sent",
                       body=f"Report for {data.po_number} emailed to {sup.name}.", link="/inventory/receive")
    await session.commit()
    return {"status": "sent", "outcome": "good" if good else "discrepancy"}


class LowStockItem(StrictModel):
    product_id: str
    product_name: str
    sku: str | None
    qty_in_stock: int
    reorder_threshold: int | None
    supplier_name: str | None
    price: float | None
    currency: str | None


@router.get("/stock/low", response_model=list[LowStockItem], summary="Products at/below their reorder point")
async def low_stock(current_user: CurrentUser, session: SessionDep) -> list[LowStockItem]:
    from sqlalchemy import or_, select  # noqa: PLC0415

    tenant_id = current_user.tenant_id
    rows = (
        await session.execute(
            select(Product).where(
                Product.tenant_id == tenant_id,
                or_(
                    Product.qty_in_stock <= func.coalesce(Product.reorder_threshold, 5),
                ),
                Product.inventory_status == "in_stock",
            ).order_by(Product.qty_in_stock)
        )
    ).scalars().all()
    out: list[LowStockItem] = []
    for p in rows:
        hist = p.price_history or []
        price: float | None = None
        if hist and isinstance(hist[-1], dict):
            pv = hist[-1].get("price")
            if pv is not None:
                with contextlib.suppress(TypeError, ValueError):
                    price = float(pv)
        out.append(LowStockItem(
            product_id=p.product_id, product_name=p.product_name, sku=p.sku,
            qty_in_stock=p.qty_in_stock, reorder_threshold=p.reorder_threshold,
            supplier_name=(p.supplier_names or [None])[0], price=price, currency=p.currency,
        ))
    return out


class StockItem(StrictModel):
    product_id: str
    product_name: str
    sku: str | None
    qty_in_stock: int
    storefront_qty: int
    reorder_threshold: int | None
    low: bool
    supplier_name: str | None
    price: float | None
    currency: str | None


@router.get("/stock", response_model=list[StockItem], summary="All in-stock products (with low-stock flag)")
async def list_stock(current_user: CurrentUser, session: SessionDep) -> list[StockItem]:
    from sqlalchemy import select  # noqa: PLC0415

    rows = (
        await session.execute(
            select(Product).where(
                Product.tenant_id == current_user.tenant_id, Product.qty_in_stock > 0
            ).order_by(Product.qty_in_stock)
        )
    ).scalars().all()
    out: list[StockItem] = []
    for p in rows:
        hist = p.price_history or []
        price: float | None = None
        if hist and isinstance(hist[-1], dict):
            pv = hist[-1].get("price")
            if pv is not None:
                with contextlib.suppress(TypeError, ValueError):
                    price = float(pv)
        threshold = p.reorder_threshold
        out.append(StockItem(
            product_id=p.product_id, product_name=p.product_name, sku=p.sku,
            qty_in_stock=p.qty_in_stock, storefront_qty=p.storefront_qty,
            reorder_threshold=threshold, low=p.qty_in_stock <= (threshold if threshold is not None else 5),
            supplier_name=(p.supplier_names or [None])[0], price=price, currency=p.currency,
        ))
    return out


class ThresholdRequest(StrictModel):
    reorder_threshold: int


@router.post("/products/{product_id}/threshold", summary="Set a product's reorder (low-stock) threshold")
async def set_threshold(
    product_id: str, body: ThresholdRequest, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    await session.execute(
        update(Product).where(
            Product.tenant_id == current_user.tenant_id, Product.product_id == product_id
        ).values(reorder_threshold=max(0, body.reorder_threshold))
    )
    await session.commit()
    return {"status": "ok"}


class RestockRequest(StrictModel):
    quantity: int = 10
    supplier_id: str | None = None


@router.post("/products/{product_id}/restock", summary="Draft a restock PO to the product's supplier (HITL)")
async def restock_product(
    product_id: str, body: RestockRequest, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    from app.infra.db.repos.product_repo import ProductRepository  # noqa: PLC0415

    tenant_id = current_user.tenant_id
    product_repo = ProductRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)
    order_repo = OrderRepository(session, tenant_id)

    product = await product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    supplier = None
    if body.supplier_id:
        supplier = await supplier_repo.get_by_id(body.supplier_id)
    if supplier is None:
        names = product.supplier_names or []
        if names:
            supplier = await supplier_repo.find_by_name_exact(str(names[0]))
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No source supplier on file for this product — pick one.")
    hist = product.price_history or []
    unit = 0.0
    if hist and isinstance(hist[-1], dict) and hist[-1].get("price") is not None:
        with contextlib.suppress(TypeError, ValueError):
            unit = float(hist[-1]["price"])
    draft = await order_repo.create_draft(
        order_id=uuid.uuid4().hex, supplier_id=supplier.supplier_id,
        line_items=[{"product_id": product_id, "product_name": product.product_name,
                     "sku": product.sku, "quantity": max(1, body.quantity), "unit_price": unit,
                     "currency": supplier.currency}],
        notes=f"Restock — low stock ({product.qty_in_stock} left)",
    )
    await session.commit()
    result = await place_order(draft.order_id, current_user, session)
    return {"order_id": draft.order_id, "hitl_action_id": result.get("hitl_action_id", ""), "status": "drafted"}


# ── Storefront Publishing ──────────────────────────────────────────────────────


class PublishProductRequest(StrictModel):
    retail_price: float
    storefront_qty: int


class PublishProductResponse(StrictModel):
    product_id: str
    storefront_status: str
    retail_price: float
    storefront_qty: int


@router.post(
    "/products/{product_id}/publish",
    response_model=PublishProductResponse,
    summary="Publish a product to the storefront with retail price and quantity",
)
async def publish_product(
    product_id: str,
    body: PublishProductRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> PublishProductResponse:
    from sqlalchemy import select

    tenant_id = current_user.tenant_id
    result = await session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.product_id == product_id,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    if product.qty_in_stock < body.storefront_qty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Storefront qty ({body.storefront_qty}) exceeds in-stock qty ({product.qty_in_stock}).",
        )

    await session.execute(
        update(Product)
        .where(
            Product.tenant_id == tenant_id,
            Product.product_id == product_id,
        )
        .values(
            retail_price=body.retail_price,
            storefront_qty=body.storefront_qty,
            storefront_status="published",
        )
    )
    await session.commit()

    logger.info("product_published", product_id=product_id, retail_price=body.retail_price)
    return PublishProductResponse(
        product_id=product_id,
        storefront_status="published",
        retail_price=body.retail_price,
        storefront_qty=body.storefront_qty,
    )


@router.delete(
    "/products/{product_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unpublish a product from the storefront",
)
async def unpublish_product(
    product_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    tenant_id = current_user.tenant_id
    await session.execute(
        update(Product)
        .where(
            Product.tenant_id == tenant_id,
            Product.product_id == product_id,
        )
        .values(storefront_status="not_published")
    )
    await session.commit()


# ── Supplier Dispute (Track 2) ─────────────────────────────────────────────────


class FileDisputeRequest(StrictModel):
    damaged_items: list[dict[str, Any]]
    damage_description: str
    po_reference: str | None = None


class FileDisputeResponse(StrictModel):
    hitl_action_id: str
    action_type: str
    status: str


@router.post(
    "/shipments/{shipment_id}/dispute",
    response_model=FileDisputeResponse,
    status_code=status.HTTP_201_CREATED,
    summary=(
        "File a supplier dispute for damaged goods received on this shipment "
        "(creates dispute_letter HITL action — Track 2)"
    ),
)
async def file_supplier_dispute(
    shipment_id: str,
    body: FileDisputeRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> FileDisputeResponse:
    """
    Creates a dispute_letter HITL action. The Communication Agent (Phase 8) will
    draft a formal complaint in the supplier's language; for now GPT-4o drafts it
    directly. Nothing is sent until the importer approves in the HITL center.
    HITL Rule: no external write without explicit importer approval.
    """
    tenant_id = current_user.tenant_id
    shipment_repo = ShipmentRepository(session, tenant_id)
    order_repo = OrderRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)

    shipment = await shipment_repo.get_by_id(shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found.")

    # Resolve supplier from PO
    supplier_name = "Supplier"
    supplier_email = ""
    supplier_language = "en"
    if shipment.po_id:
        po_list = await order_repo.list_purchase_orders()
        for po in po_list:
            if po.po_id == shipment.po_id:
                sup = await supplier_repo.get_by_id(po.supplier_id)
                if sup:
                    supplier_name = sup.name
                    supplier_email = sup.email or ""
                    supplier_language = sup.language
                break

    po_ref = body.po_reference or (shipment.po_id or "N/A")

    try:
        dispute_prompt = _load_prompt("dispute_letter")
        system_prompt = dispute_prompt.get("system", "You are a procurement specialist.")
        system_prompt = system_prompt.format(language=supplier_language)
        user_prompt = dispute_prompt.get("draft_dispute", "").format(
            supplier_name=supplier_name,
            po_reference=po_ref,
            shipment_id=shipment_id,
            damaged_items=str(body.damaged_items),
            damage_description=body.damage_description,
        )
    except Exception:
        system_prompt = f"You are a procurement specialist. Write in {supplier_language}."
        user_prompt = (
            f"Draft a formal supplier dispute letter. Supplier: {supplier_name}. "
            f"PO: {po_ref}. Shipment: {shipment_id}. "
            f"Damages: {body.damage_description}. Items: {body.damaged_items}."
        )

    draft_text = await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    action_id = uuid.uuid4().hex
    await hitl_repo.create(
        action_id=action_id,
        action_type="dispute_letter",
        payload={
            "shipment_id": shipment_id,
            "po_reference": po_ref,
            "supplier_name": supplier_name,
            "to": supplier_email,
            "subject": f"Formal Dispute — Shipment {shipment_id}",
            "body": draft_text,
            "language": supplier_language,
            "damaged_items": body.damaged_items,
            "damage_description": body.damage_description,
        },
    )
    await session.commit()

    logger.info("dispute_hitl_created", action_id=action_id, shipment_id=shipment_id)
    return FileDisputeResponse(
        hitl_action_id=action_id,
        action_type="dispute_letter",
        status="pending",
    )
