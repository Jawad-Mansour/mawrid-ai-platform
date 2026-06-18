"""
Feature:  Supplier Intelligence
Layer:    Infra / DB Models
Module:   app.infra.db.models.supplier
Purpose:  SQLAlchemy ORM model for suppliers table. Includes embedding column
          (1536-dim) for TF-IDF + embedding similarity matching waterfall.
          Delivery events stored in separate table for scorer feature extraction.
Depends:  app.infra.db.base, sqlalchemy, pgvector
HITL:     None — model only.
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Float, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Supplier(TenantMixin, Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 1), nullable=True)
    moq: Mapped[int | None] = mapped_column(nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    discrepancy_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    damage_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    # Supplier & Factory Network columns
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    offering: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)  # new | used | both
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="supplier")
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="saved")
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'active' = a supplier we do business with; 'prospect' = discovered/outreach only.
    relationship: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    outreach_messages: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
