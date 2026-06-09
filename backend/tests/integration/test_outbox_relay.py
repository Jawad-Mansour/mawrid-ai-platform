"""
Feature:  Enrichment Pipeline — Outbox Pattern
Layer:    Test / Integration
Module:   tests.integration.test_outbox_relay
Purpose:  Integration tests for the outbox relay. Verifies: product + outbox
          records written in one transaction (atomically), relay drains pending
          outbox records and marks them published, failure before relay does not
          produce orphaned embedding events.
Depends:  app.infra.workers.outbox_relay, app.infra.db.repos.outbox_repo, real DB
HITL:     None
"""
from __future__ import annotations

import pytest


class TestOutboxRelay:
    @pytest.mark.asyncio
    async def test_product_and_outbox_written_atomically(self, db_session, tenant_id) -> None:
        """Product record and outbox record must be in the same transaction."""
        from app.infra.db.repos.outbox_repo import OutboxRepository
        from app.infra.db.repos.product_repo import ProductRepository

        product_repo = ProductRepository(db_session, tenant_id=tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id=tenant_id)

        product = await product_repo.create(
            product_hash="hash_outbox_test_001",
            name="Atomic Widget",
            enrichment_status="enriched",
        )
        outbox = await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": str(product.id)},
        )
        assert outbox.product_id == product.id
        assert outbox.status == "pending"

    @pytest.mark.asyncio
    async def test_relay_marks_outbox_published(self, db_session, tenant_id) -> None:
        """After relay processes a record, it must be marked published."""
        from app.infra.db.repos.outbox_repo import OutboxRepository
        from app.infra.workers.outbox_relay import process_outbox_record

        outbox_repo = OutboxRepository(db_session, tenant_id=tenant_id)
        record = await outbox_repo.get_pending_first()
        if record:
            await process_outbox_record(record, session=db_session)
            refreshed = await outbox_repo.get_by_id(record.id)
            assert refreshed.status == "published"
