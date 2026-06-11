"""
Feature:  Catalog Enrichment Pipeline (Failure Handling)
Layer:    Infra / DB Models
Module:   app.infra.db.models.review_queue
Purpose:  SQLAlchemy ORM model for the `review_queue` table. Rows that fail
          extraction or validation are written here instead of creating a broken
          product record. The importer can inspect raw_row, fix data, and
          re-submit. No product row is created until the row passes review.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only (importer reviews via admin UI).
"""

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class ReviewQueueItem(TenantMixin, Base):
    __tablename__ = "review_queue"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    raw_row: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending_review")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
