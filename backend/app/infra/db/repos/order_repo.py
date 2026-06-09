"""
Feature:  Order Management & Procurement
Layer:    Infra / Repository
Module:   app.infra.db.repos.order_repo
Purpose:  Data access for order drafts and purchase orders. Handles draft
          grouping by supplier, status transitions (draft→submitted→pending_hitl
          →sent→confirmed), and idempotent upsert on receiving events.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.order
HITL:     None — repository only.
"""

from app.infra.db.repos.base_repo import TenantRepository


class OrderRepository(TenantRepository):
    pass
