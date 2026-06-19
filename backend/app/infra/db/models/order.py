"""
Feature:  Order Management & Procurement / Customer-Facing Storefront
Layer:    Infra / DB Models
Module:   app.infra.db.models.order
Purpose:  SQLAlchemy ORM models for OrderDraft, PurchaseOrder, Shipment,
          GoodsReceived (procurement) and StorefrontOrder (consumer).
          Line items stored as JSONB. status columns drive HITL gating.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from typing import Any

from sqlalchemy import JSON, Date, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class OrderDraft(TenantMixin, Base):
    __tablename__ = "order_drafts"

    order_id: Mapped[str] = mapped_column(primary_key=True)
    supplier_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
    line_items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_delivery_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseOrder(TenantMixin, Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[str] = mapped_column(primary_key=True)
    order_draft_id: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_id: Mapped[str] = mapped_column(Text, nullable=False)
    po_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending_hitl")
    line_items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    requested_delivery_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    po_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hitl_action_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Email thread: list of {direction, sender, body, at}
    messages: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Shipment(TenantMixin, Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(primary_key=True)
    po_id: Mapped[str] = mapped_column(Text, nullable=False)
    carrier: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_arrival_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    # exact arrival datetime (Beirut wall-clock, stored as timestamptz)
    expected_arrival_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending_shipment")
    received_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoodsReceived(TenantMixin, Base):
    __tablename__ = "goods_received"

    receiving_id: Mapped[str] = mapped_column(primary_key=True)
    shipment_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    line_items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StorefrontOrder(TenantMixin, Base):
    __tablename__ = "storefront_orders"

    order_id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    payment_gateway: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending_payment")
    items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
