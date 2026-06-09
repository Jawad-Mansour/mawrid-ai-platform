"""
Feature:  Order Management & Procurement / Customer-Facing Storefront
Layer:    Infra / DB Models
Module:   app.infra.db.models.order
Purpose:  SQLAlchemy ORM models for OrderDraft (procurement) and StorefrontOrder
          (consumer). Line items stored as JSONB. status column drives HITL
          gating (draft → pending_hitl → sent → confirmed → shipped → received).
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""
from typing import Any

from sqlalchemy import JSON, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class OrderDraft(TenantMixin, Base):
    __tablename__ = "order_drafts"

    order_id: Mapped[str] = mapped_column(primary_key=True)
    supplier_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
    line_items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StorefrontOrder(TenantMixin, Base):
    __tablename__ = "storefront_orders"

    order_id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    payment_gateway: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending_payment")
    items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
