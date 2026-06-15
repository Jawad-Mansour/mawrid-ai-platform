"""
Feature:  Order Management & Procurement
Layer:    Infra / Repository
Module:   app.infra.db.repos.order_repo
Purpose:  Data access for order_drafts and purchase_orders. Draft grouping by
          supplier, status transitions (draft→submitted→pending_hitl→sent→confirmed),
          and idempotent upsert. get_by_id always tenant-filtered.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.order
HITL:     None — repository only.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select, update

from app.infra.db.coerce import to_date
from app.infra.db.models.order import OrderDraft, PurchaseOrder
from app.infra.db.repos.base_repo import TenantRepository


class OrderRepository(TenantRepository):
    async def create_draft(
        self,
        order_id: str,
        supplier_id: str,
        line_items: list[dict[str, Any]],
        notes: str | None = None,
        desired_delivery_date: str | date | None = None,
    ) -> OrderDraft:
        draft = OrderDraft(
            order_id=order_id,
            tenant_id=self._tenant_id,
            supplier_id=supplier_id,
            status="draft",
            line_items=line_items,
            notes=notes,
            desired_delivery_date=to_date(desired_delivery_date),
        )
        self._session.add(draft)
        await self._session.flush()
        return draft

    async def get_draft_by_id(self, order_id: str) -> OrderDraft | None:
        result = await self._session.execute(
            select(OrderDraft).where(
                self._tenant_filter(OrderDraft),
                OrderDraft.order_id == order_id,
            )
        )
        return result.scalar_one_or_none()

    # Keep alias used by integration test
    async def get_by_id(self, order_id: str) -> OrderDraft | None:
        return await self.get_draft_by_id(order_id)

    async def list_drafts(self, status: str | None = None) -> list[OrderDraft]:
        q = select(OrderDraft).where(self._tenant_filter(OrderDraft))
        if status:
            q = q.where(OrderDraft.status == status)
        q = q.order_by(OrderDraft.created_at.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update_draft(
        self,
        order_id: str,
        line_items: list[dict[str, Any]] | None = None,
        notes: str | None = None,
        desired_delivery_date: str | date | None = None,
    ) -> None:
        values: dict[str, Any] = {}
        if line_items is not None:
            values["line_items"] = line_items
        if notes is not None:
            values["notes"] = notes
        if desired_delivery_date is not None:
            values["desired_delivery_date"] = to_date(desired_delivery_date)
        if values:
            await self._session.execute(
                update(OrderDraft)
                .where(
                    self._tenant_filter(OrderDraft),
                    OrderDraft.order_id == order_id,
                )
                .values(**values)
            )

    async def set_draft_status(self, order_id: str, new_status: str) -> None:
        await self._session.execute(
            update(OrderDraft)
            .where(
                self._tenant_filter(OrderDraft),
                OrderDraft.order_id == order_id,
            )
            .values(status=new_status)
        )

    async def create_purchase_order(
        self,
        po_id: str,
        order_draft_id: str,
        supplier_id: str,
        po_number: str,
        line_items: list[dict[str, Any]],
        po_text: str,
        hitl_action_id: str,
        currency: str = "USD",
        total_amount: float | None = None,
        requested_delivery_date: str | date | None = None,
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            po_id=po_id,
            tenant_id=self._tenant_id,
            order_draft_id=order_draft_id,
            supplier_id=supplier_id,
            po_number=po_number,
            status="pending_hitl",
            line_items=line_items,
            po_text=po_text,
            hitl_action_id=hitl_action_id,
            currency=currency,
            total_amount=total_amount,
            requested_delivery_date=to_date(requested_delivery_date),
        )
        self._session.add(po)
        await self._session.flush()
        return po

    async def get_po_by_id(self, po_id: str) -> PurchaseOrder | None:
        result = await self._session.execute(
            select(PurchaseOrder).where(
                self._tenant_filter(PurchaseOrder),
                PurchaseOrder.po_id == po_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_purchase_orders(self) -> list[PurchaseOrder]:
        result = await self._session.execute(
            select(PurchaseOrder)
            .where(self._tenant_filter(PurchaseOrder))
            .order_by(PurchaseOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def set_po_status(self, po_id: str, new_status: str) -> None:
        await self._session.execute(
            update(PurchaseOrder)
            .where(
                self._tenant_filter(PurchaseOrder),
                PurchaseOrder.po_id == po_id,
            )
            .values(status=new_status)
        )
