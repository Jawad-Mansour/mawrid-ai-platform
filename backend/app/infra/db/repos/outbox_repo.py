"""
Feature:  Catalog Enrichment Pipeline (Outbox Pattern)
Layer:    Infra / Repository
Module:   app.infra.db.repos.outbox_repo
Purpose:  Data access for the outbox table. Relay reads unprocessed rows,
          marks each processed atomically after successful pgvector write.
          Used by outbox_relay worker process — never by the FastAPI app.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.outbox
HITL:     None — repository only.
"""
from app.infra.db.repos.base_repo import TenantRepository


class OutboxRepository(TenantRepository):
    pass
