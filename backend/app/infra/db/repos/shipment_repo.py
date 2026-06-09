"""
Feature:  Order Management & Procurement
Layer:    Infra / Repository
Module:   app.infra.db.repos.shipment_repo
Purpose:  Data access for shipments and goods-received events. Idempotency:
          a receiving event for a given shipment can only be submitted once
          (409 on second attempt). Tracks container status through all stages.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.order
HITL:     None — repository only.
"""

from app.infra.db.repos.base_repo import TenantRepository


class ShipmentRepository(TenantRepository):
    pass
