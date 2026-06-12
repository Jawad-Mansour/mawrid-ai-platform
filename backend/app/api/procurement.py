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

import uuid
from datetime import UTC, date, datetime
from typing import Any

import structlog
import yaml
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import update

from app.api.deps import CurrentUser, SessionDep
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
            line_items_json=str(line_items),
            payment_terms="NET 30",
            delivery_address="",
            notes=notes or "",
        )
    except Exception:
        system_prompt = f"You are a procurement specialist. Language: {language}."
        user_prompt = (
            f"Draft a purchase order for {supplier_name}. PO #{po_number}. "
            f"Items: {line_items}. Delivery by: {delivery_date or 'TBD'}."
        )

    return await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=2048,
    )


# ── Order Drafts ───────────────────────────────────────────────────────────────


class DraftLineItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    currency: str = "USD"


class CreateDraftRequest(BaseModel):
    supplier_id: str
    line_items: list[DraftLineItem]
    notes: str | None = None
    desired_delivery_date: str | None = None


class OrderDraftResponse(BaseModel):
    order_id: str
    supplier_id: str
    status: str
    line_items: list[Any]
    notes: str | None
    desired_delivery_date: str | None
    created_at: str


class UpdateDraftRequest(BaseModel):
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found."
        )

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
        desired_delivery_date=str(draft.desired_delivery_date) if draft.desired_delivery_date else None,
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
        desired_delivery_date=str(draft.desired_delivery_date) if draft.desired_delivery_date else None,
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
        desired_delivery_date=str(updated.desired_delivery_date) if updated.desired_delivery_date else None,
        created_at=str(updated.created_at),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found."
        )

    po_id = uuid.uuid4().hex
    po_number = f"PO-{datetime.now(UTC).strftime('%Y%m%d')}-{po_id[:6].upper()}"

    line_items: list[dict[str, Any]] = draft.line_items or []
    total = sum(
        int(item.get("quantity", 0)) * float(item.get("unit_price", 0))
        for item in line_items
    )

    po_text = await _draft_po_text(
        supplier_name=supplier.name,
        tenant_name=tenant_id,
        po_number=po_number,
        line_items=line_items,
        delivery_date=str(draft.desired_delivery_date) if draft.desired_delivery_date else None,
        language=supplier.language,
        notes=draft.notes,
    )

    hitl_action_id = uuid.uuid4().hex
    action = await hitl_repo.create(
        action_id=hitl_action_id,
        action_type="purchase_order_send",
        payload={
            "po_id": po_id,
            "po_number": po_number,
            "supplier_name": supplier.name,
            "to": supplier.email or "",
            "subject": f"Purchase Order {po_number}",
            "body": po_text,
            "language": supplier.language,
            "total": total,
            "currency": supplier.currency,
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
        requested_delivery_date=str(draft.desired_delivery_date) if draft.desired_delivery_date else None,
    )

    await order_repo.set_draft_status(order_id, "pending_hitl")
    await session.commit()

    logger.info("purchase_order_created", po_id=po_id, hitl_action_id=hitl_action_id)
    return {
        "po_id": po_id,
        "hitl_action_id": hitl_action_id,
        "status": "pending_hitl",
        "po_number": po_number,
    }


# ── Purchase Orders ────────────────────────────────────────────────────────────


class PurchaseOrderResponse(BaseModel):
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


# ── Shipments ──────────────────────────────────────────────────────────────────


class CreateShipmentRequest(BaseModel):
    po_id: str
    carrier: str | None = None
    tracking_number: str | None = None
    expected_arrival_date: str | None = None


class ShipmentResponse(BaseModel):
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
        expected_arrival_date=str(shipment.expected_arrival_date) if shipment.expected_arrival_date else None,
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


class UpdateShipmentStatusRequest(BaseModel):
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


class ReceivedItemInput(BaseModel):
    product_id: str
    qty_received: int
    qty_damaged: int = 0


class ReceiveGoodsRequest(BaseModel):
    items: list[ReceivedItemInput]
    notes: str | None = None


class ReceiveGoodsResponse(BaseModel):
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


# ── Storefront Publishing ──────────────────────────────────────────────────────


class PublishProductRequest(BaseModel):
    retail_price: float
    storefront_qty: int


class PublishProductResponse(BaseModel):
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


class FileDisputeRequest(BaseModel):
    damaged_items: list[dict[str, Any]]
    damage_description: str
    po_reference: str | None = None


class FileDisputeResponse(BaseModel):
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
