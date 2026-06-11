"""
Feature:  Catalog Enrichment Pipeline (Failure Handling)
Layer:    Infra / Repository
Module:   app.infra.db.repos.review_queue_repo
Purpose:  Data access for the review_queue table. Writes rows that failed
          GPT-4o extraction so the importer can inspect and re-submit.
          No product record is created for items in this table.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.review_queue
HITL:     None — repository only.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.infra.db.models.review_queue import ReviewQueueItem
from app.infra.db.repos.base_repo import TenantRepository


class ReviewQueueRepository(TenantRepository):
    async def add(
        self,
        document_id: str,
        raw_row: dict[str, object],
        failure_reason: str,
    ) -> ReviewQueueItem:
        item = ReviewQueueItem(
            id=uuid.uuid4().hex,
            tenant_id=self._tenant_id,
            document_id=document_id,
            raw_row=raw_row,
            failure_reason=failure_reason,
            status="pending_review",
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_by_document(self, document_id: str) -> list[ReviewQueueItem]:
        result = await self._session.execute(
            select(ReviewQueueItem).where(
                self._tenant_filter(ReviewQueueItem),
                ReviewQueueItem.document_id == document_id,
            )
        )
        return list(result.scalars().all())
