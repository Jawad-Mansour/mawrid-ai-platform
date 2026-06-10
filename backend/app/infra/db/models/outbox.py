"""
Feature:  Catalog Enrichment Pipeline (Outbox Pattern)
Layer:    Infra / DB Models
Module:   app.infra.db.models.outbox
Purpose:  SQLAlchemy ORM model for the `outbox` table. Stores embedding
          generation events written atomically with the product record.
          The outbox relay drains this table: generates embedding →
          writes to pgvector → marks row processed. Crash-safe: each row
          is marked processed only after successful pgvector write.
          No dual-write — DB commit + queue publish is forbidden.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — infrastructure only.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class OutboxEvent(TenantMixin, Base):
    __tablename__ = "outbox"

    event_id: Mapped[str] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_outbox_unprocessed", "tenant_id", "processed"),)
