"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Infra / Repository
Module:   app.infra.db.repos.dunning_repo
Purpose:  Data access for invoices and dunning sequences. Key operation:
          payment auto-stop transaction (marks invoice paid AND cancels all
          pending dunning HITL actions in single atomic write — no partial state).
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.invoice
HITL:     None — repository triggers HITL creation via service layer.
"""

from app.infra.db.repos.base_repo import TenantRepository


class DunningRepository(TenantRepository):
    pass
