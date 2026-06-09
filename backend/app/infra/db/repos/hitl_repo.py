"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Infra / Repository
Module:   app.infra.db.repos.hitl_repo
Purpose:  Data access for hitl_actions table: create, status transitions (with
          optimistic locking), list pending by action_type, expire stale actions,
          and audit trail queries. All queries include tenant_id filter.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.hitl_action
HITL:     This IS the HITL data layer.
"""
from app.infra.db.repos.base_repo import TenantRepository


class HITLRepository(TenantRepository):
    pass
