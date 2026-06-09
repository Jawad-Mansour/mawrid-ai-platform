"""
Feature:  Multi-Tenant Isolation (cross-cutting)
Layer:    Infra / Repository
Module:   app.infra.db.repos.base_repo
Purpose:  TenantRepository base class. ALL repository methods prepend
          `WHERE tenant_id = :tenant_id` to every query. Subclasses MUST
          call super().__init__(session, tenant_id). This is the second
          isolation layer (PostgreSQL RLS is the first).
Depends:  sqlalchemy, app.infra.db.session
HITL:     None — infrastructure only.
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class TenantRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def _tenant_filter(self, model_class: Any) -> Any:
        """Returns a WHERE clause fragment that filters by tenant_id."""
        return model_class.tenant_id == self._tenant_id
