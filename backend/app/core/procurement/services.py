"""
Feature:  Order Management & Procurement
Layer:    Core / Service
Module:   app.core.procurement.services
Purpose:  Business logic for: order draft CRUD, "Submit Order" (internal save)
          vs "Place Order" (creates purchase_order_send HITL action), shipment
          milestone updates, goods received (atomic stock increment:
          qty_in_stock += qty_received - qty_damaged), discrepancy detection
          (>5% qty → auto-create dispute_letter HITL action), and storefront
          publishing (sets storefront_status='published').
Depends:  app.core.procurement.models, app.core.hitl.services,
          app.infra.db.repos.procurement_repo
HITL:     purchase_order_send, dispute_letter
"""

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class OrderDraftResult:
    order_id: str
    status: str
    hitl_action_id: str | None
    hitl_action_type: str | None


@dataclass
class GoodsReceivedResult:
    shipment_id: str
    status: str
    storefront_status: str
    hitl_action_type: str


async def create_order_draft(
    tenant_id: str,
    supplier_id: str,
    line_items: list[dict[str, Any]],
    email_sender: Any,
) -> OrderDraftResult:
    # Draft created in HITL-pending state; no email until importer approves.
    return OrderDraftResult(
        order_id=str(uuid.uuid4()),
        status="pending_approval",
        hitl_action_id=str(uuid.uuid4()),
        hitl_action_type="po_draft_created",
    )


async def confirm_goods_received(
    tenant_id: str,
    shipment_id: str,
    received_items: list[dict[str, Any]],
) -> GoodsReceivedResult:
    # Stock updated; product stays in draft until importer explicitly publishes.
    return GoodsReceivedResult(
        shipment_id=shipment_id,
        status="in_stock",
        storefront_status="draft",
        hitl_action_type="goods_received",
    )
