# mypy: ignore-errors
"""
Feature:  Enrichment Pipeline — ARQ Queue
Layer:    Test / Integration
Module:   tests.integration.test_queue_idempotency
Purpose:  Integration tests for ARQ job idempotency. Verifies: submitting the
          same product_hash twice yields the same job id (ARQ dedups on _job_id),
          and different hashes yield different jobs. Real Redis required.
Depends:  app.infra.workers.enrichment_worker, arq, redis
HITL:     None
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from arq import create_pool
from arq.connections import RedisSettings


@pytest_asyncio.fixture
async def arq_pool() -> AsyncGenerator[Any, None]:
    pool = await create_pool(
        RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
    )
    yield pool
    await pool.aclose()


class TestEnrichmentQueueIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_job_is_noop(self, arq_pool: Any, tenant_id: str) -> None:
        """Enqueueing the same product_hash twice must yield the same job id."""
        from app.infra.workers.enrichment_worker import enqueue_enrichment

        product_hash = "sha256_test_idempotency_001"
        job1 = await enqueue_enrichment(
            arq_pool, tenant_id=tenant_id, product_hash=product_hash, raw_text="Widget Alpha"
        )
        job2 = await enqueue_enrichment(
            arq_pool, tenant_id=tenant_id, product_hash=product_hash, raw_text="Widget Alpha"
        )
        assert job1.job_id == job2.job_id

    @pytest.mark.asyncio
    async def test_different_hash_creates_new_job(self, arq_pool: Any, tenant_id: str) -> None:
        """Different product_hash values must create separate jobs."""
        from app.infra.workers.enrichment_worker import enqueue_enrichment

        job1 = await enqueue_enrichment(
            arq_pool, tenant_id=tenant_id, product_hash="hash_alpha", raw_text="Product Alpha"
        )
        job2 = await enqueue_enrichment(
            arq_pool, tenant_id=tenant_id, product_hash="hash_beta", raw_text="Product Beta"
        )
        assert job1.job_id != job2.job_id
