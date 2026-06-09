"""
Feature:  Catalog Enrichment Pipeline
Layer:    Core / Domain Models
Module:   app.core.catalog.models
Purpose:  Pydantic v2 domain models for Product (with all three independent
          status state machines), ProductChunk (parent-doc pattern), and
          EnrichmentJob. Includes product_hash computation (SHA-256 of
          tenant_id:product_name:sku) and price_history JSONB schema.
Depends:  pydantic
HITL:     None — models only.
"""
import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    ENRICHED = "enriched"
    FAILED = "failed"
    DLQ = "dlq"


class InventoryStatus(StrEnum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


class StorefrontStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProductDomain(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: str
    tenant_id: str
    product_name: str
    sku: str | None = None
    enrichment_status: EnrichmentStatus = EnrichmentStatus.PENDING
    inventory_status: InventoryStatus = InventoryStatus.OUT_OF_STOCK
    storefront_status: StorefrontStatus = StorefrontStatus.DRAFT
    qty_in_stock: int = 0
    storefront_qty: int = 0
    price_history: list[dict[str, Any]] = []

    @model_validator(mode="after")
    def compute_hash(self) -> "ProductDomain":
        raw = f"{self.tenant_id}:{self.product_name}:{self.sku or ''}"
        self.product_hash = hashlib.sha256(raw.encode()).hexdigest()
        return self

    product_hash: str = ""
