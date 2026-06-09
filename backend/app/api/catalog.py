"""
Feature:  Catalog Enrichment Pipeline
Layer:    API / Router
Module:   app.api.catalog
Purpose:  HTTP routes for supplier document upload, enrichment status polling,
          internal catalog browse/search, barcode lookup, and DLQ management.
          Upload triggers n8n WF-02 → enrichment pipeline.
Depends:  app.core.catalog.services, app.infra.queue.client, app.api.deps
HITL:     None — enrichment is internal. Publishing is in procurement.py.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/catalog", tags=["catalog"])
