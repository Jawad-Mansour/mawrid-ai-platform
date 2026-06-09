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
