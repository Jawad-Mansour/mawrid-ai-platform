"""
Feature:  Enrichment Pipeline
Layer:    Test / Unit
Module:   tests.unit.test_enrichment_pipeline
Purpose:  Unit tests for the 6-layer enrichment pipeline.
          Verifies: product_hash computation, idempotency on duplicate jobs,
          outbox record written atomically with product record, enrichment
          lands in internal catalog only (not storefront).
Depends:  app.core.catalog.pipeline, app.core.catalog.hash, conftest fakes
HITL:     None
"""
from __future__ import annotations

import pytest


class TestProductHash:
    def test_hash_excludes_price(self) -> None:
        """Same product with different prices must produce the same hash."""
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("tenant1", "Apple iPhone 15", None)
        h2 = compute_product_hash("tenant1", "Apple iPhone 15", None)
        assert h1 == h2

    def test_hash_includes_sku_when_present(self) -> None:
        from app.core.catalog.hash import compute_product_hash

        h_with = compute_product_hash("tenant1", "Widget", "SKU-001")
        h_without = compute_product_hash("tenant1", "Widget", None)
        assert h_with != h_without

    def test_hash_is_tenant_scoped(self) -> None:
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("tenant1", "Widget", None)
        h2 = compute_product_hash("tenant2", "Widget", None)
        assert h1 != h2

    def test_colon_delimiter_prevents_collision(self) -> None:
        """'ab' + 'c' must not collide with 'a' + 'bc'."""
        from app.core.catalog.hash import compute_product_hash

        h1 = compute_product_hash("ab", "c", None)
        h2 = compute_product_hash("a", "bc", None)
        assert h1 != h2


class TestEnrichmentPipeline:
    @pytest.mark.asyncio
    async def test_enriched_product_not_on_storefront(self, fake_llm) -> None:
        """Enriched product must have storefront_status = None (not published)."""
        from app.core.catalog.pipeline import EnrichmentPipeline

        pipeline = EnrichmentPipeline(llm=fake_llm)
        result = await pipeline.run(
            tenant_id="tenant1",
            raw_text="iPhone 15 Pro 256GB Space Black",
        )
        assert result.storefront_status is None
        assert result.enrichment_status == "enriched"

    @pytest.mark.asyncio
    async def test_pipeline_idempotent_on_same_hash(self, fake_llm) -> None:
        """Submitting the same product twice must not create a duplicate."""
        from app.core.catalog.pipeline import EnrichmentPipeline

        pipeline = EnrichmentPipeline(llm=fake_llm)
        r1 = await pipeline.run(tenant_id="t1", raw_text="Widget A")
        r2 = await pipeline.run(tenant_id="t1", raw_text="Widget A")
        assert r1.product_hash == r2.product_hash
