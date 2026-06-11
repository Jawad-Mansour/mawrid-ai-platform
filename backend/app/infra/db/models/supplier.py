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

from pgvector.sqlalchemy import Vector
from sqlalchemy import Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Supplier(TenantMixin, Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="en")
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
