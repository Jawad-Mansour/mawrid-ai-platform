"""
Feature:  Supplier Intelligence
Layer:    Infra / Repository
Module:   app.infra.db.repos.supplier_repo
Purpose:  Data access for suppliers and delivery events. Includes embedding
          similarity search for matching waterfall (≥0.9 auto-match, 0.3–0.9
          HITL, <0.3 HITL "create new supplier?").
Depends:  app.infra.db.repos.base_repo
HITL:     None — repository only.
"""
from app.infra.db.repos.base_repo import TenantRepository


class SupplierRepository(TenantRepository):
    pass
