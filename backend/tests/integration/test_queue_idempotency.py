"""
Feature:  Enrichment Pipeline — ARQ Queue
Layer:    Test / Integration
Module:   tests.integration.test_queue_idempotency
Purpose:  Integration tests for ARQ job idempotency. Verifies: submitting the
          same product_hash twice enqueues only one job, the second enqueue
          returns the existing job ID, real Redis required.
Depends:  app.infra.workers.enrichment_worker, arq, redis
HITL:     None
"""
from __future__ import annotations

import pytest


class TestEnrichmentQueueIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_job_is_noop(self, redis_client, tenant_id) -> None:
        """Enqueueing the same product_hash twice must not create duplicate jobs."""
        from app.infra.workers.enrichment_worker import enqueue_enrichment

        product_hash = "sha256_test_idempotency_001"

        job1 = await enqueue_enrichment(
            redis=redis_client,
            tenant_id=tenant_id,
            product_hash=product_hash,
            raw_text="Widget Alpha",
        )
        job2 = await enqueue_enrichment(
            redis=redis_client,
            tenant_id=tenant_id,
            product_hash=product_hash,
            raw_text="Widget Alpha",
        )
        assert job1.id == job2.id

    @pytest.mark.asyncio
    async def test_different_hash_creates_new_job(self, redis_client, tenant_id) -> None:
        """Different product_hash values must create separate jobs."""
        from app.infra.workers.enrichment_worker import enqueue_enrichment

        job1 = await enqueue_enrichment(
            redis=redis_client,
            tenant_id=tenant_id,
            product_hash="hash_alpha",
            raw_text="Product Alpha",
        )
        job2 = await enqueue_enrichment(
            redis=redis_client,
            tenant_id=tenant_id,
            product_hash="hash_beta",
            raw_text="Product Beta",
        )
        assert job1.id != job2.id
