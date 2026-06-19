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

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, update

from app.infra.db.coerce import to_date
from app.infra.db.models.order import GoodsReceived, Shipment
from app.infra.db.repos.base_repo import TenantRepository


def _to_dt(value: str | datetime | None) -> datetime | None:
    """Parse an ISO datetime (e.g. '2026-06-25T14:30' from a datetime-local input). The value
    is the importer's Beirut wall-clock; we tag it UTC so the numbers round-trip exactly and
    the UI shows them verbatim (labelled 'Beirut time')."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return None


class ShipmentRepository(TenantRepository):
    async def create(
        self,
        shipment_id: str,
        po_id: str,
        carrier: str | None = None,
        tracking_number: str | None = None,
        expected_arrival_date: str | date | None = None,
        expected_arrival_at: str | datetime | None = None,
    ) -> Shipment:
        shipment = Shipment(
            shipment_id=shipment_id,
            tenant_id=self._tenant_id,
            po_id=po_id,
            carrier=carrier,
            tracking_number=tracking_number,
            expected_arrival_date=to_date(expected_arrival_date),
            expected_arrival_at=_to_dt(expected_arrival_at),
            status="pending_shipment",
        )
        self._session.add(shipment)
        await self._session.flush()
        return shipment

    async def update_arrival_at(self, shipment_id: str, expected_arrival_at: str | datetime) -> None:
        await self._session.execute(
            update(Shipment)
            .where(self._tenant_filter(Shipment), Shipment.shipment_id == shipment_id)
            .values(expected_arrival_at=_to_dt(expected_arrival_at))
        )

    async def get_by_id(self, shipment_id: str) -> Shipment | None:
        result = await self._session.execute(
            select(Shipment).where(
                self._tenant_filter(Shipment),
                Shipment.shipment_id == shipment_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_po(self, po_id: str) -> list[Shipment]:
        result = await self._session.execute(
            select(Shipment).where(
                self._tenant_filter(Shipment),
                Shipment.po_id == po_id,
            )
        )
        return list(result.scalars().all())

    async def list_all(self, status: str | None = None) -> list[Shipment]:
        q = select(Shipment).where(self._tenant_filter(Shipment))
        if status:
            q = q.where(Shipment.status == status)
        q = q.order_by(Shipment.created_at.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def set_status(self, shipment_id: str, new_status: str) -> None:
        values: dict[str, Any] = {"status": new_status}
        if new_status == "arrived":
            values["received_at"] = datetime.now(UTC)
        await self._session.execute(
            update(Shipment)
            .where(
                self._tenant_filter(Shipment),
                Shipment.shipment_id == shipment_id,
            )
            .values(**values)
        )

    async def update_arrival_date(
        self, shipment_id: str, expected_arrival_date: str | date
    ) -> None:
        await self._session.execute(
            update(Shipment)
            .where(
                self._tenant_filter(Shipment),
                Shipment.shipment_id == shipment_id,
            )
            .values(expected_arrival_date=to_date(expected_arrival_date))
        )

    async def get_receiving(self, shipment_id: str) -> GoodsReceived | None:
        result = await self._session.execute(
            select(GoodsReceived).where(
                self._tenant_filter(GoodsReceived),
                GoodsReceived.shipment_id == shipment_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_receiving(
        self,
        receiving_id: str,
        shipment_id: str,
        line_items: list[dict[str, Any]],
        received_by: str,
        notes: str | None = None,
    ) -> GoodsReceived:
        receiving = GoodsReceived(
            receiving_id=receiving_id,
            tenant_id=self._tenant_id,
            shipment_id=shipment_id,
            line_items=line_items,
            received_by=received_by,
            notes=notes,
        )
        self._session.add(receiving)
        await self._session.flush()
        return receiving
