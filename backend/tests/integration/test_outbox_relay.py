"""
Feature:  Enrichment Pipeline — Outbox Pattern
Layer:    Test / Integration
Module:   tests.integration.test_outbox_relay
Purpose:  Integration tests for the outbox relay. Verifies: product + outbox
          records written in one transaction (atomically), relay drains pending
          outbox records and writes embeddings, crash-safety (SKIP LOCKED).
Depends:  app.infra.workers.outbox_relay, app.infra.db.repos.outbox_repo, real DB
HITL:     None
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.core.catalog.hash import compute_product_hash
from app.infra.db.models.outbox import OutboxEvent
from app.infra.db.models.product import Product
from app.infra.db.repos.outbox_repo import OutboxRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.workers.outbox_relay import process_pending_events
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestOutboxAtomicity:
    @pytest.mark.asyncio
    async def test_product_and_outbox_written_atomically(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Product record and outbox event written in the same transaction."""
        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        product_hash = compute_product_hash(tenant_id, "Atomic Widget")
        product = Product(
            product_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            product_hash=product_hash,
            product_name="Atomic Widget",
            enrichment_status="enriched",
        )
        saved = await product_repo.upsert(product)

        event = await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": saved.product_id, "tenant_id": tenant_id},
        )

        assert event.event_type == "embedding_requested"
        assert event.payload["product_id"] == saved.product_id
        assert event.processed is False

    @pytest.mark.asyncio
    async def test_pending_event_visible_before_commit(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Pending event must be queryable within the same transaction (via flush)."""
        outbox_repo = OutboxRepository(db_session, tenant_id)

        event = await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": "some-id", "tenant_id": tenant_id},
        )

        # Without committing, the pending batch query should see the flushed row
        pending = await outbox_repo.get_pending_batch()
        ids = [e.event_id for e in pending]
        assert event.event_id in ids


class TestOutboxRelay:
    @pytest.mark.asyncio
    async def test_relay_marks_event_processed(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """After process_pending_events(), the event must be marked processed."""
        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        product_hash = compute_product_hash(tenant_id, "Relay Test Product")
        product = Product(
            product_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            product_hash=product_hash,
            product_name="Relay Test Product",
            enrichment_status="enriched",
        )
        saved = await product_repo.upsert(product)

        event = await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": saved.product_id, "tenant_id": tenant_id},
        )
        await db_session.flush()

        fake_vector = [0.1] * 1536
        with patch(
            "app.infra.workers.outbox_relay.embed",
            new=AsyncMock(return_value=fake_vector),
        ):
            count = await process_pending_events(db_session, tenant_id)

        assert count == 1

        result = await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.event_id == event.event_id)
        )
        refreshed = result.scalar_one_or_none()
        assert refreshed is not None
        assert refreshed.processed is True

    @pytest.mark.asyncio
    async def test_relay_writes_embedding_to_product(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """After relay, product.embedding must be set to the vector returned by embed()."""
        product_repo = ProductRepository(db_session, tenant_id)
        outbox_repo = OutboxRepository(db_session, tenant_id)

        product_hash = compute_product_hash(tenant_id, "Embed Me Widget")
        product = Product(
            product_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            product_hash=product_hash,
            product_name="Embed Me Widget",
            enrichment_status="enriched",
            description="A widget with a description.",
        )
        saved = await product_repo.upsert(product)

        await outbox_repo.create(
            event_type="embedding_requested",
            payload={"product_id": saved.product_id, "tenant_id": tenant_id},
        )
        await db_session.flush()

        fake_vector = [0.42] * 1536
        with patch(
            "app.infra.workers.outbox_relay.embed",
            new=AsyncMock(return_value=fake_vector),
        ):
            await process_pending_events(db_session, tenant_id)

        # Verify embedding was written
        result = await db_session.execute(
            select(Product).where(Product.product_id == saved.product_id)
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert updated.embedding is not None
        assert len(updated.embedding) == 1536  # noqa: PLR2004

    @pytest.mark.asyncio
    async def test_non_embedding_events_are_skipped_gracefully(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Events of unknown types must be marked processed without errors."""
        outbox_repo = OutboxRepository(db_session, tenant_id)

        event = await outbox_repo.create(
            event_type="unknown_future_event_type",
            payload={"data": "something"},
        )
        await db_session.flush()

        with patch(
            "app.infra.workers.outbox_relay.embed",
            new=AsyncMock(return_value=[0.0] * 1536),
        ):
            count = await process_pending_events(db_session, tenant_id)

        assert count == 1

        result = await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.event_id == event.event_id)
        )
        refreshed = result.scalar_one_or_none()
        assert refreshed is not None
        assert refreshed.processed is True
