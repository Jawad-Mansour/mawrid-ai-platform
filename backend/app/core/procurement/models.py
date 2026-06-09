"""
Feature:  Order Management & Procurement
Layer:    Core / Domain Models
Module:   app.core.procurement.models
Purpose:  Pydantic v2 domain models for OrderDraft (importer-created), PurchaseOrder
          (after HITL approval), Shipment, GoodsReceived (atomic stock update:
          qty_in_stock += qty_received - qty_damaged), and StorefrontPublishRequest.
Depends:  pydantic
HITL:     purchase_order_send, dispute_letter
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class OrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING_HITL = "pending_hitl"
    SENT = "sent"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    RECEIVED = "received"
    DISPUTED = "disputed"


class OrderDraft(BaseModel):
    model_config = {"extra": "forbid"}

    order_id: str
    tenant_id: str
    supplier_id: str
    line_items: list[dict[str, Any]]
    status: OrderStatus = OrderStatus.DRAFT


class GoodsReceived(BaseModel):
    model_config = {"extra": "forbid"}

    order_id: str
    tenant_id: str
    line_items: list[dict[str, Any]]  # [{product_id, qty_received, qty_damaged}]
    # qty_in_stock += qty_received - qty_damaged (atomic DB transaction)
