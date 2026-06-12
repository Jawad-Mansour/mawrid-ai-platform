"""
Feature:  Supplier Intelligence
Layer:    Infra / DB Models
Module:   app.infra.db.models.delivery_event
Purpose:  SQLAlchemy ORM model for supplier_delivery_events table.
          Each row captures one delivery: promised vs actual date, items
          ordered/received/damaged, agreed vs billed price, and response time.
          These 6 derived features feed the Ridge regression supplier scorer.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class SupplierDeliveryEvent(TenantMixin, Base):
    __tablename__ = "supplier_delivery_events"

    delivery_event_id: Mapped[str] = mapped_column(primary_key=True)
    supplier_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    items_ordered: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    items_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_damaged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    price_agreed: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default="0")
    price_billed: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    response_time_hours: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
