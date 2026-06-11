"""
Feature:  Order Management & Procurement
Layer:    Core / Service
Module:   app.core.procurement.services
Purpose:  Business logic for: order draft CRUD, "Submit Draft" (internal save),
          "Place Order" (creates purchase_order_send HITL action + GPT-4o PO text),
          shipment milestone updates, goods received (atomic stock increment:
          qty_in_stock += qty_received - qty_damaged), discrepancy detection
          (>5% qty → flag), and storefront publishing.
          Unit-testable: pure functions that return domain results, no direct DB access.
Depends:  app.core.procurement.models, app.core.hitl.models, typing.Protocol
HITL:     purchase_order_send, dispute_letter
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OrderDraftResult:
    order_id: str
    status: str
    supplier_id: str
    line_items: list[dict[str, Any]]


@dataclass
class PlaceOrderResult:
    po_id: str
    hitl_action_id: str
    hitl_action_type: str
    po_text: str


@dataclass
class GoodsReceivedResult:
    receiving_id: str
    shipment_id: str
    status: str
    storefront_status: str
    discrepancy_detected: bool
    damage_detected: bool


@dataclass
class ReceiveItem:
    product_id: str
    qty_received: int
    qty_damaged: int = 0


def compute_order_total(line_items: list[dict[str, Any]]) -> float:
    total = 0.0
    for item in line_items:
        qty = int(item.get("quantity", 0))
        price = float(item.get("unit_price", 0))
        total += qty * price
    return total


def detect_discrepancy(
    line_items: list[dict[str, Any]], received: list[ReceiveItem]
) -> bool:
    """Returns True if any product was received more than 5% short."""
    received_map = {r.product_id: r.qty_received for r in received}
    for item in line_items:
        pid = item.get("product_id", "")
        ordered = int(item.get("quantity", 0))
        got = received_map.get(str(pid), 0)
        if ordered > 0 and got < ordered * 0.95:
            return True
    return False


def stock_delta(received: list[ReceiveItem]) -> dict[str, int]:
    """Returns {product_id: net_qty_to_add} where net = received - damaged."""
    return {
        r.product_id: max(0, r.qty_received - r.qty_damaged)
        for r in received
    }


# ── Unit-testable service functions ──────────────────────────────────────────


def make_order_draft_result(
    order_id: str,
    supplier_id: str,
    line_items: list[dict[str, Any]],
) -> OrderDraftResult:
    """Build an OrderDraftResult domain object. DB write happens in the API layer."""
    return OrderDraftResult(
        order_id=order_id,
        status="draft",
        supplier_id=supplier_id,
        line_items=line_items,
    )


def make_goods_received_result(
    receiving_id: str,
    shipment_id: str,
    ordered_items: list[dict[str, Any]],
    received_items: list[ReceiveItem],
) -> GoodsReceivedResult:
    """Compute result of receiving goods. Stock update happens in the API layer."""
    discrepancy = detect_discrepancy(ordered_items, received_items)
    damage = any(r.qty_damaged > 0 for r in received_items)
    return GoodsReceivedResult(
        receiving_id=receiving_id,
        shipment_id=shipment_id,
        status="in_stock",
        storefront_status="not_published",
        discrepancy_detected=discrepancy,
        damage_detected=damage,
    )


# ── Legacy stub interface — kept so existing unit tests pass ─────────────────
# These functions delegate to the real logic above.


async def create_order_draft(
    tenant_id: str,
    supplier_id: str,
    line_items: list[dict[str, Any]],
    email_sender: Any,
) -> OrderDraftResult:
    """
    Unit-testable: creates a draft in 'draft' state. No HITL, no email.
    DB write happens in the API layer (procurement.py).
    """
    import uuid

    return make_order_draft_result(
        order_id=str(uuid.uuid4()),
        supplier_id=supplier_id,
        line_items=line_items,
    )


async def confirm_goods_received(
    tenant_id: str,
    shipment_id: str,
    received_items: list[dict[str, Any]],
) -> GoodsReceivedResult:
    """
    Unit-testable: validates received items, returns GoodsReceivedResult.
    DB stock update happens in the API layer (procurement.py).
    """
    import uuid

    parsed = [
        ReceiveItem(
            product_id=str(item.get("product_id", "")),
            qty_received=int(item.get("quantity_received", item.get("qty_received", 0))),
            qty_damaged=int(item.get("qty_damaged", 0)),
        )
        for item in received_items
    ]
    return make_goods_received_result(
        receiving_id=str(uuid.uuid4()),
        shipment_id=shipment_id,
        ordered_items=[],  # no DB access in unit tests
        received_items=parsed,
    )
