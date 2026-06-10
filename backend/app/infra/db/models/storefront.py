"""
Feature:  Customer-Facing Store
Layer:    Infra / DB Models
Module:   app.infra.db.models.storefront
Purpose:  SQLAlchemy ORM models for `consumer_orders` and `consumer_order_items`.
          Consumer orders are created at checkout. Consumer purchases decrement
          storefront_qty (not qty_in_stock directly). Fulfillment status is
          tracked independently of inventory status. Payment is via Stripe/OMT/Whish.
Depends:  app.infra.db.base, sqlalchemy
HITL:     fulfillment_notification (on order fulfillment update)
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class ConsumerOrder(TenantMixin, Base):
    __tablename__ = "consumer_orders"

    order_id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    payment_gateway: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsumerOrderItem(TenantMixin, Base):
    __tablename__ = "consumer_order_items"

    item_id: Mapped[str] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("consumer_orders.order_id"), nullable=False)
    product_id: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
