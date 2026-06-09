"""
Feature:  Catalog Enrichment Pipeline (cross-cutting)
Layer:    Infra / Queue
Module:   app.infra.queue.client
Purpose:  ARQ Redis job queue client. Provides enqueue_enrichment_job() with
          job key = product_hash (idempotent — duplicate enqueue is no-op).
          Also used for HITL execution dispatch after approval.
Depends:  arq, redis
HITL:     None — queue infrastructure only.
"""
