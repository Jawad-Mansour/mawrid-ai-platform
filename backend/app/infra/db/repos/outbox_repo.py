"""
Feature:  Catalog Enrichment Pipeline (Outbox Pattern)
Layer:    Infra / Repository
Module:   app.infra.db.repos.outbox_repo
Purpose:  Data access for the outbox table. Crash-safe batch retrieval uses
          FOR UPDATE SKIP LOCKED — two relay instances cannot claim the same event.
          Events are marked processed atomically with the embedding write.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.outbox
HITL:     None — infrastructure only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.infra.db.models.outbox import OutboxEvent
from app.infra.db.repos.base_repo import TenantRepository


class OutboxRepository(TenantRepository):
    async def create(
        self,
        event_type: str,
        payload: dict[str, object],
    ) -> OutboxEvent:
        event = OutboxEvent(
            event_id=uuid.uuid4().hex,
            tenant_id=self._tenant_id,
            event_type=event_type,
            payload=payload,
            processed=False,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_pending_batch(self, limit: int = 50) -> list[OutboxEvent]:
        """Return up to `limit` unprocessed events, locked for exclusive update."""
        result = await self._session.execute(
            select(OutboxEvent)
            .where(
                self._tenant_filter(OutboxEvent),
                OutboxEvent.processed == False,  # noqa: E712
            )
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_processed(self, event_id: str) -> None:
        await self._session.execute(
            update(OutboxEvent)
            .where(
                self._tenant_filter(OutboxEvent),
                OutboxEvent.event_id == event_id,
            )
            .values(processed=True, processed_at=datetime.now(tz=UTC))
        )
