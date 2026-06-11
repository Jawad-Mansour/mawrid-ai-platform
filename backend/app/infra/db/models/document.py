"""
Feature:  Catalog Enrichment Pipeline (Document Ingestion)
Layer:    Infra / DB Models
Module:   app.infra.db.models.document
Purpose:  SQLAlchemy ORM model for the `documents` table. Tracks every uploaded
          supplier document (PDF or Excel). document_id = SHA-256(file_bytes),
          which serves as both primary key and dedup key. Status transitions:
          pending → processing → completed | failed.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Document(TenantMixin, Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(Text, primary_key=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    row_counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parsed_rows: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
