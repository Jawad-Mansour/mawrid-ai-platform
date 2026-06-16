"""
Feature:  Catalog Enrichment Pipeline (Document Ingestion)
Layer:    Infra / Repository
Module:   app.infra.db.repos.document_repo
Purpose:  Data access for the documents table. Provides idempotent upsert
          (document_id = SHA-256 of file bytes prevents re-processing the same
          file twice), status transitions, and listing by status.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.document
HITL:     None — repository only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.infra.db.models.document import Document
from app.infra.db.repos.base_repo import TenantRepository


class DocumentRepository(TenantRepository):
    async def get_by_id(self, document_id: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                self._tenant_filter(Document),
                Document.document_id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 100) -> list[Document]:
        """All uploaded sheets for this tenant, newest first (upload history)."""
        result = await self._session.execute(
            select(Document)
            .where(self._tenant_filter(Document))
            .order_by(Document.uploaded_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert(self, document: Document) -> Document:
        existing = await self.get_by_id(document.document_id)
        if existing is not None:
            return existing
        self._session.add(document)
        await self._session.flush()
        return document

    async def update_status(
        self,
        document_id: str,
        status: str,
        row_counts: dict[str, object] | None = None,
        parsed_rows: list[dict[str, object]] | None = None,
    ) -> None:
        values: dict[str, object] = {"status": status}
        if status == "completed":
            values["completed_at"] = datetime.now(tz=UTC)
        if row_counts is not None:
            values["row_counts"] = row_counts
        if parsed_rows is not None:
            values["parsed_rows"] = parsed_rows
        await self._session.execute(
            update(Document)
            .where(
                self._tenant_filter(Document),
                Document.document_id == document_id,
            )
            .values(**values)
        )
