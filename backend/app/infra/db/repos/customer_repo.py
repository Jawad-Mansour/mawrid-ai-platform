"""
Feature:  Customer Management
Layer:    Infra / Repository
Module:   app.infra.db.repos.customer_repo
Purpose:  Data access for customers. Implements exact-match lookups (email,
          phone) for the 3-tier matching waterfall used in Phase 7.
          Phase 6 uses get_by_id for reading customer dunning features
          (segment, language, payment_history_score, previous_dunning_count).
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.customer
HITL:     None — repository only.
"""

from __future__ import annotations

from sqlalchemy import select, update

from app.infra.db.models.customer import Customer
from app.infra.db.repos.base_repo import TenantRepository


class CustomerRepository(TenantRepository):
    async def get_by_id(self, customer_id: str) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                self._tenant_filter(Customer),
                Customer.customer_id == customer_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                self._tenant_filter(Customer),
                Customer.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, customer: Customer) -> Customer:
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def increment_dunning_count(self, customer_id: str) -> None:
        """Atomically increment previous_dunning_count by 1."""
        from sqlalchemy import text  # noqa: PLC0415

        await self._session.execute(
            update(Customer)
            .where(
                self._tenant_filter(Customer),
                Customer.customer_id == customer_id,
            )
            .values(
                previous_dunning_count=text("previous_dunning_count + 1")
            )
        )

    async def reset_dunning_count(self, customer_id: str) -> None:
        """Reset previous_dunning_count to 0 on payment."""
        await self._session.execute(
            update(Customer)
            .where(
                self._tenant_filter(Customer),
                Customer.customer_id == customer_id,
            )
            .values(previous_dunning_count=0)
        )

    async def get_by_phone(self, phone: str) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                self._tenant_filter(Customer),
                Customer.phone == phone,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 500) -> list[Customer]:
        result = await self._session.execute(
            select(Customer)
            .where(self._tenant_filter(Customer))
            .order_by(Customer.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_segment(self, customer_id: str, segment: str) -> None:
        await self._session.execute(
            update(Customer)
            .where(
                self._tenant_filter(Customer),
                Customer.customer_id == customer_id,
            )
            .values(segment=segment)
        )

    async def update_payment_history_score(self, customer_id: str, new_score: float) -> None:
        await self._session.execute(
            update(Customer)
            .where(
                self._tenant_filter(Customer),
                Customer.customer_id == customer_id,
            )
            .values(payment_history_score=new_score)
        )
