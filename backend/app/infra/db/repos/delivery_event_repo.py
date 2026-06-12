"""
Feature:  Supplier Intelligence
Layer:    Infra / Repository
Module:   app.infra.db.repos.delivery_event_repo
Purpose:  Data access for supplier_delivery_events. Records individual delivery
          performance events and computes the 6 features used by the supplier
          scorer (on_time_rate, damage_rate, avg_price_vs_market,
          response_time_hours, discrepancy_rate, catalog_completeness).
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.delivery_event
HITL:     None — repository only.
"""

from __future__ import annotations

from sqlalchemy import select

from app.infra.db.models.delivery_event import SupplierDeliveryEvent
from app.infra.db.repos.base_repo import TenantRepository


class DeliveryEventRepository(TenantRepository):
    async def create(self, event: SupplierDeliveryEvent) -> SupplierDeliveryEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_by_supplier(self, supplier_id: str) -> list[SupplierDeliveryEvent]:
        result = await self._session.execute(
            select(SupplierDeliveryEvent)
            .where(
                self._tenant_filter(SupplierDeliveryEvent),
                SupplierDeliveryEvent.supplier_id == supplier_id,
            )
            .order_by(SupplierDeliveryEvent.created_at)
        )
        return list(result.scalars().all())
