"""
Feature:  Dunning Engine (4 Tracks) / Invoice Management
Layer:    Infra / DB Models
Module:   app.infra.db.models.dunning
Purpose:  SQLAlchemy ORM models for the `invoices` and `dunning_sequences` tables.
          Invoice direction distinguishes payable (Track 1) from receivable (Track 3/4).
          paid_at populated atomically on payment webhook (same transaction that
          cancels pending dunning HITL actions). DunningSequence tracks which
          track is running and its HITL status per invoice.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Invoice(TenantMixin, Base):
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)  # payable | receivable
    invoice_type: Mapped[str] = mapped_column(Text, nullable=False)  # b2b | b2c
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(default=30)
    status: Mapped[str] = mapped_column(
        Text, default="unpaid", nullable=False
    )  # unpaid | paid | reconciled
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # MinIO object key
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Contact fallback — used when no supplier_id / customer_id FK is set
    contact_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional FK references — linked when the invoice is created from an order/customer
    customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Order reference for B2C invoices (Track 4 payment link uses this)
    order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Currency for display in dunning messages
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")


class DunningSequence(TenantMixin, Base):
    __tablename__ = "dunning_sequences"

    sequence_id: Mapped[str] = mapped_column(primary_key=True)
    invoice_id: Mapped[str] = mapped_column(Text, nullable=False)
    track: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # payables | disputes | receivables | b2c
    status: Mapped[str] = mapped_column(
        Text, default="active", nullable=False
    )  # active | stopped | completed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
