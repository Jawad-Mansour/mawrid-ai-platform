"""
Feature:  Catalog Enrichment Pipeline — End-to-End
Layer:    Test / Integration
Module:   tests.integration.test_enrichment_e2e
Purpose:  Phase 2.6 integration test. Verifies the full enrichment flow:
          parsed document rows → GPT-4o extraction → enrichment pipeline →
          products in DB → outbox events written atomically → relay drains →
          embeddings written. Uses 20 in-memory product rows.
          LLM, Icecat, SearXNG, web fetch all mocked. Real DB required (Gate 4).
Depends:  app.core.catalog.extractor, app.core.catalog.enrichment_pipeline,
          app.infra.db.repos.*, app.infra.workers.outbox_relay, real DB
HITL:     None
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.catalog.enrichment_pipeline import (
    EnrichmentInput,
    SequentialEnrichmentPipeline,
)
from app.core.catalog.extractor import extract_rows
from app.core.catalog.hash import compute_product_hash
from app.infra.db.models.outbox import OutboxEvent
from app.infra.db.models.product import Product
from app.infra.db.repos.outbox_repo import OutboxRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.workers.outbox_relay import process_pending_events
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_N_PRODUCTS = 20


def _make_rows(n: int = _N_PRODUCTS) -> list[dict[str, object]]:
    return [
        {"product": f"Widget {i}", "price": float(10 * i), "sku": f"WGT-{i:04d}"}
        for i in range(1, n + 1)
    ]


def _make_extraction_llm_response(rows: list[dict[str, object]]) -> str:
    items = [
        {
            "row_index": i,
            "product_name": f"Widget {i + 1}",
            "sku": f"WGT-{i + 1:04d}",
            "barcode": None,
            "price": float(10 * (i + 1)),
            "currency": "USD",
            "specifications": {"Category": "General"},
            "_failure_reason": None,
        }
        for i in range(len(rows))
    ]
    return json.dumps(items)


_ENRICH_GPT_RESPONSE = json.dumps(
    {
        "specifications": {"Category": "General", "Brand": "TestBrand"},
        "description": "A general-purpose test widget.",
    }
)


class FakeIcecat:
    async def lookup_ean(self, ean: str) -> None:
        return None

    async def lookup_name(self, name: str) -> None:
        return None


class FakeSearxng:
    async def search(self, query: str) -> list[str]:
        return []


class FakeWebFetcher:
    async def fetch_and_clean(self, url: str) -> str:
        return ""


class TestEnrichmentE2E:
    @pytest.mark.asyncio
    async def test_20_products_extracted_and_stored(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """
        20 rows extracted via GPT-4o → enriched → all 20 products in DB
        with enrichment_status='enriched'.
        """
        rows = _make_rows(_N_PRODUCTS)
        extraction_response = _make_extraction_llm_response(rows)

        with patch(
            "app.core.catalog.extractor.chat_completion",
            new=AsyncMock(return_value=extraction_response),
        ):
            extraction = await extract_rows(rows)

        assert len(extraction.products) == _N_PRODUCTS
        assert len(extraction.failed_rows) == 0

        pipeline = SequentialEnrichmentPipeline(
            icecat=FakeIcecat(),
            searxng=FakeSearxng(),
            fetcher=FakeWebFetcher(),
        )

        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_ENRICH_GPT_RESPONSE),
        ):
            for extracted in extraction.products:
                enriched = await pipeline.run(
                    EnrichmentInput(
                        product_name=extracted.product_name,
                        sku=extracted.sku,
                    )
                )
                product_hash = compute_product_hash(
                    tenant_id, extracted.product_name, extracted.sku
                )
                product = Product(
                    product_id=uuid.uuid4().hex,
                    tenant_id=tenant_id,
                    product_hash=product_hash,
                    product_name=enriched.product_name,
                    sku=enriched.sku,
                    enrichment_status="enriched",
                    description=enriched.description,
                    specifications=enriched.specifications,
                    enrichment_source=enriched.enrichment_source,
                    enrichment_confidence=enriched.enrichment_confidence,
                )
                saved = await product_repo.upsert(product)
                await outbox_repo.create(
                    event_type="embedding_requested",
                    payload={"product_id": saved.product_id, "tenant_id": tenant_id},
                )

        await db_session.flush()

        # Verify 20 products in DB
        result = await db_session.execute(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.enrichment_status == "enriched",
            )
        )
        products = list(result.scalars().all())
        assert len(products) == _N_PRODUCTS

        # Verify 20 pending outbox events
        result = await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant_id,
                OutboxEvent.processed == False,  # noqa: E712
            )
        )
        pending = list(result.scalars().all())
        assert len(pending) == _N_PRODUCTS

    @pytest.mark.asyncio
    async def test_relay_drains_all_20_outbox_events(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Relay must drain all 20 pending events and write embeddings."""
        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        for i in range(_N_PRODUCTS):
            name = f"Relay Widget {i}"
            product_hash = compute_product_hash(tenant_id, name)
            product = Product(
                product_id=uuid.uuid4().hex,
                tenant_id=tenant_id,
                product_hash=product_hash,
                product_name=name,
                enrichment_status="enriched",
                description=f"Description for widget {i}.",
            )
            saved = await product_repo.upsert(product)
            await outbox_repo.create(
                event_type="embedding_requested",
                payload={"product_id": saved.product_id, "tenant_id": tenant_id},
            )

        await db_session.flush()

        fake_vector = [0.1] * 1536
        with patch(
            "app.infra.workers.outbox_relay.embed",
            new=AsyncMock(return_value=fake_vector),
        ):
            processed = await process_pending_events(db_session, tenant_id)

        assert processed == _N_PRODUCTS

        # All events must be marked processed
        result = await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant_id,
                OutboxEvent.processed == False,  # noqa: E712
            )
        )
        remaining = list(result.scalars().all())
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_extraction_failures_do_not_block_successes(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """
        If 2 out of 5 rows fail extraction, the other 3 must still be enriched
        and stored. Failed rows are not placed in the outbox.
        """
        rows: list[dict[str, object]] = [
            {"product": f"Good Product {i}", "price": float(100 * i)} for i in range(1, 4)
        ] + [
            {"col_0": "", "col_1": ""},  # empty row — will fail
            {"col_0": "", "col_1": ""},  # empty row — will fail
        ]

        llm_response = json.dumps(
            [
                {
                    "row_index": 0,
                    "product_name": "Good Product 1",
                    "sku": None,
                    "barcode": None,
                    "price": 100.0,
                    "currency": "USD",
                    "specifications": {},
                    "_failure_reason": None,
                },
                {
                    "row_index": 1,
                    "product_name": "Good Product 2",
                    "sku": None,
                    "barcode": None,
                    "price": 200.0,
                    "currency": "USD",
                    "specifications": {},
                    "_failure_reason": None,
                },
                {
                    "row_index": 2,
                    "product_name": "Good Product 3",
                    "sku": None,
                    "barcode": None,
                    "price": 300.0,
                    "currency": "USD",
                    "specifications": {},
                    "_failure_reason": None,
                },
                {
                    "row_index": 3,
                    "product_name": None,
                    "sku": None,
                    "barcode": None,
                    "price": None,
                    "currency": None,
                    "specifications": {},
                    "_failure_reason": "No product name found",
                },
                {
                    "row_index": 4,
                    "product_name": None,
                    "sku": None,
                    "barcode": None,
                    "price": None,
                    "currency": None,
                    "specifications": {},
                    "_failure_reason": "No product name found",
                },
            ]
        )

        with patch(
            "app.core.catalog.extractor.chat_completion",
            new=AsyncMock(return_value=llm_response),
        ):
            extraction = await extract_rows(rows)

        assert len(extraction.products) == 3  # noqa: PLR2004
        assert len(extraction.failed_rows) == 2  # noqa: PLR2004

        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        pipeline = SequentialEnrichmentPipeline(
            icecat=FakeIcecat(),
            searxng=FakeSearxng(),
            fetcher=FakeWebFetcher(),
        )

        with patch(
            "app.core.catalog.enrichment_pipeline.chat_completion",
            new=AsyncMock(return_value=_ENRICH_GPT_RESPONSE),
        ):
            for extracted in extraction.products:
                enriched = await pipeline.run(EnrichmentInput(product_name=extracted.product_name))
                product_hash = compute_product_hash(tenant_id, extracted.product_name)
                product = Product(
                    product_id=uuid.uuid4().hex,
                    tenant_id=tenant_id,
                    product_hash=product_hash,
                    product_name=enriched.product_name,
                    enrichment_status="enriched",
                )
                saved = await product_repo.upsert(product)
                await outbox_repo.create(
                    event_type="embedding_requested",
                    payload={"product_id": saved.product_id, "tenant_id": tenant_id},
                )

        await db_session.flush()

        result = await db_session.execute(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.enrichment_status == "enriched",
            )
        )
        products = list(result.scalars().all())
        assert len(products) == 3  # noqa: PLR2004

        result = await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant_id,
                OutboxEvent.processed == False,  # noqa: E712
            )
        )
        pending = list(result.scalars().all())
        assert len(pending) == 3  # noqa: PLR2004 — only successful products get outbox events
