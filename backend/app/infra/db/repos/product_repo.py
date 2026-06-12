"""
Feature:  Catalog Enrichment Pipeline
Layer:    Infra / Repository
Module:   app.infra.db.repos.product_repo
Purpose:  Data access for product catalog: upsert by product_hash (idempotent),
          status transitions, pgvector HNSW similarity search with mandatory
          tenant_id filter (third isolation layer for embeddings).
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.product
HITL:     None — repository only.
"""

from __future__ import annotations

from sqlalchemy import select, update

from app.infra.db.models.product import Product
from app.infra.db.repos.base_repo import TenantRepository


class ProductRepository(TenantRepository):
    async def get_by_hash(self, product_hash: str) -> Product | None:
        result = await self._session.execute(
            select(Product).where(
                self._tenant_filter(Product),
                Product.product_hash == product_hash,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, product_id: str) -> Product | None:
        result = await self._session.execute(
            select(Product).where(
                self._tenant_filter(Product),
                Product.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, product: Product) -> Product:
        existing = await self.get_by_hash(product.product_hash)
        if existing is not None:
            # Update mutable fields; preserve hash and IDs
            existing.product_name = product.product_name
            existing.sku = product.sku
            existing.barcode = product.barcode
            # Phase 2 enrichment fields — only overwrite if provided
            if product.description is not None:
                existing.description = product.description
            if product.specifications is not None:
                existing.specifications = product.specifications
            if product.image_path is not None:
                existing.image_path = product.image_path
            if product.enrichment_source is not None:
                existing.enrichment_source = product.enrichment_source
            if product.enrichment_confidence is not None:
                existing.enrichment_confidence = product.enrichment_confidence
            if product.currency is not None:
                existing.currency = product.currency
            if product.price_history:
                existing.price_history = product.price_history
            await self._session.flush()
            return existing
        self._session.add(product)
        await self._session.flush()
        return product

    async def set_enrichment_status(self, product_id: str, status: str) -> None:
        await self._session.execute(
            update(Product)
            .where(
                self._tenant_filter(Product),
                Product.product_id == product_id,
            )
            .values(enrichment_status=status)
        )

    async def set_inventory_status(self, product_id: str, status: str) -> None:
        await self._session.execute(
            update(Product)
            .where(
                self._tenant_filter(Product),
                Product.product_id == product_id,
            )
            .values(inventory_status=status)
        )

    async def set_storefront_status(self, product_id: str, status: str) -> None:
        await self._session.execute(
            update(Product)
            .where(
                self._tenant_filter(Product),
                Product.product_id == product_id,
            )
            .values(storefront_status=status)
        )

    async def list_all(self, limit: int = 50) -> list[Product]:
        result = await self._session.execute(
            select(Product)
            .where(self._tenant_filter(Product))
            .order_by(Product.product_name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_barcode(self, barcode: str) -> Product | None:
        result = await self._session.execute(
            select(Product).where(
                self._tenant_filter(Product),
                Product.barcode == barcode,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_enrichment(self, limit: int = 50) -> list[Product]:
        result = await self._session.execute(
            select(Product)
            .where(
                self._tenant_filter(Product),
                Product.enrichment_status == "pending",
            )
            .limit(limit)
        )
        return list(result.scalars().all())
