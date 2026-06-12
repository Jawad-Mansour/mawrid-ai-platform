"""
Feature:  Customer-Facing Store
Layer:    Infra / Repository
Module:   app.infra.db.repos.consumer_order_repo
Purpose:  Data access for consumer_orders and consumer_order_items.
          Provides list, get, create, and status-transition operations.
          All queries scoped to tenant_id via TenantRepository base.
Depends:  app.infra.db.models.storefront, app.infra.db.repos.base_repo
HITL:     None — repository only (HITL actions created in admin API).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, update

from app.infra.db.models.storefront import ConsumerOrder, ConsumerOrderItem
from app.infra.db.repos.base_repo import TenantRepository


class ConsumerOrderRepository(TenantRepository):
    async def get_by_id(self, order_id: str) -> ConsumerOrder | None:
        result = await self._session.execute(
            select(ConsumerOrder).where(
                self._tenant_filter(ConsumerOrder),
                ConsumerOrder.order_id == order_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        limit: int = 100,
        status: str | None = None,
    ) -> list[ConsumerOrder]:
        q = select(ConsumerOrder).where(self._tenant_filter(ConsumerOrder))
        if status:
            q = q.where(ConsumerOrder.status == status)
        q = q.order_by(ConsumerOrder.created_at.desc()).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def create(
        self,
        order_id: str,
        customer_id: str,
        payment_gateway: str,
        total_amount: Decimal,
        status: str = "pending",
    ) -> ConsumerOrder:
        order = ConsumerOrder(
            order_id=order_id,
            tenant_id=self._tenant_id,
            customer_id=customer_id,
            status=status,
            payment_gateway=payment_gateway,
            total_amount=total_amount,
        )
        self._session.add(order)
        await self._session.flush()
        return order

    async def add_item(
        self,
        item_id: str,
        order_id: str,
        product_id: str,
        qty: int,
        unit_price: Decimal,
    ) -> ConsumerOrderItem:
        item = ConsumerOrderItem(
            item_id=item_id,
            tenant_id=self._tenant_id,
            order_id=order_id,
            product_id=product_id,
            qty=qty,
            unit_price=unit_price,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_items(self, order_id: str) -> list[ConsumerOrderItem]:
        result = await self._session.execute(
            select(ConsumerOrderItem).where(
                self._tenant_filter(ConsumerOrderItem),
                ConsumerOrderItem.order_id == order_id,
            )
        )
        return list(result.scalars().all())

    async def set_status(self, order_id: str, new_status: str) -> None:
        await self._session.execute(
            update(ConsumerOrder)
            .where(
                self._tenant_filter(ConsumerOrder),
                ConsumerOrder.order_id == order_id,
            )
            .values(status=new_status)
        )
