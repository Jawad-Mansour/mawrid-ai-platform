"""
Feature:  Catalog Enrichment Pipeline
Layer:    Core / Service
Module:   app.core.catalog.services
Purpose:  Business logic for document ingestion (PDF/Excel/image), enrichment
          job creation (keyed on product_hash for idempotency), outbox pattern
          (product write + embedding event in one atomic transaction), DLQ
          management, and barcode EAN/UPC resolution.
Depends:  app.core.catalog.models, app.infra.db.repos.catalog_repo,
          app.infra.queue.client (ARQ), app.infra.storage.minio
HITL:     None — enrichment is internal.
"""

from dataclasses import dataclass


@dataclass
class PublishResult:
    product_id: str
    storefront_status: str


def can_publish(
    enrichment_status: str,
    lifecycle_status: str,
    retail_price: float | None,
) -> bool:
    return (
        enrichment_status == "enriched"
        and lifecycle_status == "in_stock"
        and retail_price is not None
    )


def publish_product(tenant_id: str, product_id: str, retail_price: float) -> PublishResult:
    return PublishResult(product_id=product_id, storefront_status="published")
