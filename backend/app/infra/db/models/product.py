"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / DB Models
Module:   app.infra.db.models.product
Purpose:  SQLAlchemy ORM model for the `products` table. Includes all three
          independent status columns (enrichment_status, inventory_status,
          storefront_status), product_hash (unique per tenant), price_history
          JSONB, pgvector embedding column (1536-dim for OpenAI text-embedding-3-small),
          and Phase 2 enrichment columns (description, specifications, image_path,
          enrichment_source, enrichment_confidence, currency).
Depends:  app.infra.db.base, sqlalchemy, pgvector
HITL:     None — model only.
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Product(TenantMixin, Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(primary_key=True)
    product_hash: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(Text, default="pending")
    inventory_status: Mapped[str] = mapped_column(Text, default="not_ordered")
    storefront_status: Mapped[str] = mapped_column(Text, default="not_published")
    qty_in_stock: Mapped[int] = mapped_column(default=0)
    storefront_qty: Mapped[int] = mapped_column(default=0)
    retail_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reorder_threshold: Mapped[int | None] = mapped_column(nullable=True)
    price_history: Mapped[list[Any]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    # Phase 2: enrichment output columns
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specifications: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reference links gathered during enrichment (AI-overview style "sources" block)
    source_urls: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # Supplier(s) whose uploaded sheets include this product (per-supplier catalogues)
    supplier_names: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # Document(s)/sheets this product came from (per-sheet catalogues)
    document_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    enrichment_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_confidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "product_hash", name="uq_product_hash_per_tenant"),
        Index(
            "ix_product_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )
