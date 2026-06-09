"""
Feature:  Dunning Engine (4 Tracks) / Invoice Management
Layer:    Infra / DB Models
Module:   app.infra.db.models.dunning
Purpose:  SQLAlchemy ORM models for the `invoices` and `dunning_sequences` tables.
          Invoice direction distinguishes payable (Track 1) from receivable (Track 3/4).
          paid_at populated atomically on payment webhook (same transaction that
          cancels pending dunning actions). DunningSequence tracks which days have
          fired and their HITL status per invoice+track combination.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from sqlalchemy import DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Invoice(TenantMixin, Base):
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)  # payable | receivable
    invoice_type: Mapped[str] = mapped_column(Text, nullable=False)  # b2b | b2c
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    invoice_date: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(default=30)
    status: Mapped[str] = mapped_column(
        Text, default="unpaid", nullable=False
    )  # unpaid | paid | reconciled
    paid_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # MinIO object key
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DunningSequence(TenantMixin, Base):
    __tablename__ = "dunning_sequences"

    sequence_id: Mapped[str] = mapped_column(primary_key=True)
    invoice_id: Mapped[str] = mapped_column(Text, nullable=False)
    track: Mapped[int] = mapped_column(nullable=False)  # 1 | 2 | 3 | 4
    status: Mapped[str] = mapped_column(
        Text, default="active", nullable=False
    )  # active | stopped | completed
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stopped_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
