"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Infra / Repository
Module:   app.infra.db.repos.dunning_repo
Purpose:  Data access for dunning_sequences table. Sequences are created when
          a dunning track fires; stopped atomically when invoice is paid.
          Idempotency: get_active_sequence prevents duplicate sequences per
          invoice+track combination.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.dunning
HITL:     None — repository only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.infra.db.models.dunning import DunningSequence
from app.infra.db.repos.base_repo import TenantRepository


class DunningRepository(TenantRepository):
    async def create_sequence(
        self,
        sequence_id: str,
        invoice_id: str,
        track: str,
    ) -> DunningSequence:
        """Create a new active dunning sequence. Does NOT check for duplicates — caller must."""
        seq = DunningSequence(
            sequence_id=sequence_id,
            tenant_id=self._tenant_id,
            invoice_id=invoice_id,
            track=track,
            status="active",
        )
        self._session.add(seq)
        await self._session.flush()
        return seq

    async def get_active_sequence(
        self,
        invoice_id: str,
        track: str,
    ) -> DunningSequence | None:
        """Return the active sequence for invoice+track, or None if none exists."""
        result = await self._session.execute(
            select(DunningSequence).where(
                self._tenant_filter(DunningSequence),
                DunningSequence.invoice_id == invoice_id,
                DunningSequence.track == track,
                DunningSequence.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def list_by_invoice(self, invoice_id: str) -> list[DunningSequence]:
        result = await self._session.execute(
            select(DunningSequence).where(
                self._tenant_filter(DunningSequence),
                DunningSequence.invoice_id == invoice_id,
            ).order_by(DunningSequence.created_at)
        )
        return list(result.scalars().all())

    async def list_active(self, track: str | None = None) -> list[DunningSequence]:
        q = select(DunningSequence).where(
            self._tenant_filter(DunningSequence),
            DunningSequence.status == "active",
        )
        if track:
            q = q.where(DunningSequence.track == track)
        q = q.order_by(DunningSequence.created_at)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def stop_sequence(
        self,
        sequence_id: str,
        stopped_at: datetime | None = None,
    ) -> None:
        now = stopped_at or datetime.now(UTC)
        await self._session.execute(
            update(DunningSequence)
            .where(
                self._tenant_filter(DunningSequence),
                DunningSequence.sequence_id == sequence_id,
            )
            .values(status="stopped", stopped_at=now)
        )

    async def stop_all_for_invoice(
        self,
        invoice_id: str,
        stopped_at: datetime | None = None,
    ) -> int:
        """Stop all active sequences for an invoice. Returns count stopped."""
        now = stopped_at or datetime.now(UTC)
        result = await self._session.execute(
            update(DunningSequence)
            .where(
                self._tenant_filter(DunningSequence),
                DunningSequence.invoice_id == invoice_id,
                DunningSequence.status == "active",
            )
            .values(status="stopped", stopped_at=now)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
