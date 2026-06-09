"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / DB Models
Module:   app.infra.db.models.product
Purpose:  SQLAlchemy ORM model for the `products` table. Includes all three
          independent status columns (enrichment_status, inventory_status,
          storefront_status), product_hash (unique per tenant), price_history
          JSONB, and pgvector embedding column (1536-dim for text-embedding-3-small).
Depends:  app.infra.db.base, sqlalchemy, pgvector
HITL:     None — model only.
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Product(TenantMixin, Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(primary_key=True)
    product_hash: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(Text, default="pending")
    inventory_status: Mapped[str] = mapped_column(Text, default="out_of_stock")
    storefront_status: Mapped[str] = mapped_column(Text, default="draft")
    qty_in_stock: Mapped[int] = mapped_column(default=0)
    storefront_qty: Mapped[int] = mapped_column(default=0)
    price_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "product_hash", name="uq_product_hash_per_tenant"),
        Index(
            "ix_product_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )
