"""
Feature:  Invoice Management
Layer:    API / Router
Module:   app.api.invoices
Purpose:  HTTP routes for invoice listing, aging buckets, PDF download
          (presigned MinIO URL), manual paid marking, and invoice generation
          endpoint called by n8n WF-07.
Depends:  app.core.dunning.services (invoice model), app.infra.storage.minio, app.api.deps
HITL:     None — invoice reads/generation are not external write actions.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/invoices", tags=["invoices"])
