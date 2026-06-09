"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Repository
Module:   app.infra.db.repos.product_repo
Purpose:  Data access for product catalog: upsert by product_hash (idempotent),
          batch embedding store (outbox pattern — same transaction), status
          transitions, DLQ management, and pgvector HNSW similarity search
          with tenant_id filter (third isolation layer for embeddings).
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.product
HITL:     None — repository only.
"""

from app.infra.db.repos.base_repo import TenantRepository


class ProductRepository(TenantRepository):
    pass
