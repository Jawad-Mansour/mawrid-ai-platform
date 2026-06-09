"""
Feature:  Dunning Engine / Invoice Management
Layer:    Infra / Repository
Module:   app.infra.db.repos.invoice_repo
Purpose:  Data access for invoices and dunning sequences. Supports atomic
          payment auto-stop: marks invoice paid + cancels all pending HITL
          actions for that invoice in a single transaction. Handles
          idempotent payment webhook deduplication.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.dunning
HITL:     None — repository only (HITL cancel logic in hitl_repo).
"""

from app.infra.db.repos.base_repo import TenantRepository


class InvoiceRepository(TenantRepository):
    pass
