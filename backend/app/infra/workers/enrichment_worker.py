"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Workers
Module:   app.infra.workers.enrichment_worker
Purpose:  ARQ worker process for enrichment jobs. Pulls jobs from Redis queue,
          runs each product through the 6-layer pipeline (doc parse, LLM
          extraction, image analysis, barcode lookup, category classify,
          embedding), writes result + outbox event atomically in one transaction.
          Runs as a separate Docker process (not part of the FastAPI app).
Depends:  arq, app.core.catalog.services, app.infra.llm, app.infra.db
HITL:     None — enrichment is internal.
"""
