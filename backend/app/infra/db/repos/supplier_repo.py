"""
Feature:  Supplier Intelligence
Layer:    Infra / Repository
Module:   app.infra.db.repos.supplier_repo
Purpose:  Data access for suppliers. Includes basic CRUD and embedding
          similarity search for matching waterfall (≥0.9 auto-match, 0.3–0.9
          HITL, <0.3 HITL "create new supplier?").
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.supplier
HITL:     None — repository only.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from app.infra.db.models.supplier import Supplier
from app.infra.db.repos.base_repo import TenantRepository


class SupplierRepository(TenantRepository):
    async def create(
        self,
        supplier_id: str,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        language: str = "en",
        currency: str = "USD",
    ) -> Supplier:
        supplier = Supplier(
            supplier_id=supplier_id,
            tenant_id=self._tenant_id,
            name=name,
            email=email,
            phone=phone,
            language=language,
            currency=currency,
        )
        self._session.add(supplier)
        await self._session.flush()
        return supplier

    async def get_by_id(self, supplier_id: str) -> Supplier | None:
        result = await self._session.execute(
            select(Supplier).where(
                self._tenant_filter(Supplier),
                Supplier.supplier_id == supplier_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Supplier]:
        result = await self._session.execute(
            select(Supplier).where(self._tenant_filter(Supplier)).order_by(Supplier.name)
        )
        return list(result.scalars().all())

    async def update(
        self,
        supplier_id: str,
        **kwargs: Any,
    ) -> None:
        allowed = {"name", "email", "phone", "language", "currency", "score", "embedding"}
        values = {k: v for k, v in kwargs.items() if k in allowed}
        if values:
            await self._session.execute(
                update(Supplier)
                .where(
                    self._tenant_filter(Supplier),
                    Supplier.supplier_id == supplier_id,
                )
                .values(**values)
            )

    async def increment_discrepancy(self, supplier_id: str) -> None:
        await self._session.execute(
            update(Supplier)
            .where(
                self._tenant_filter(Supplier),
                Supplier.supplier_id == supplier_id,
            )
            .values(discrepancy_count=Supplier.discrepancy_count + 1)
        )

    async def increment_damage(self, supplier_id: str) -> None:
        await self._session.execute(
            update(Supplier)
            .where(
                self._tenant_filter(Supplier),
                Supplier.supplier_id == supplier_id,
            )
            .values(damage_count=Supplier.damage_count + 1)
        )

    async def find_by_name_exact(self, name: str) -> Supplier | None:
        result = await self._session.execute(
            select(Supplier).where(
                self._tenant_filter(Supplier),
                Supplier.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_best_scored(self) -> Supplier | None:
        """Return the supplier with the highest score. Used for reorder auto-selection."""
        result = await self._session.execute(
            select(Supplier)
            .where(
                self._tenant_filter(Supplier),
                Supplier.score.isnot(None),
            )
            .order_by(Supplier.score.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_with_embeddings(self) -> list[Supplier]:
        """Return suppliers that have computed embeddings for cosine matching."""
        result = await self._session.execute(
            select(Supplier).where(
                self._tenant_filter(Supplier),
                Supplier.embedding.isnot(None),
            )
        )
        return list(result.scalars().all())

    async def set_score(self, supplier_id: str, score: float) -> None:
        await self._session.execute(
            update(Supplier)
            .where(
                self._tenant_filter(Supplier),
                Supplier.supplier_id == supplier_id,
            )
            .values(score=score)
        )
