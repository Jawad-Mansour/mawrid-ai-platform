"""
Feature:  Dunning Engine / Invoice Management
Layer:    Infra / Repository
Module:   app.infra.db.repos.invoice_repo
Purpose:  Data access for invoices. Provides list methods scoped to each
          dunning track's trigger conditions. mark_paid is called inside
          auto_stop_on_payment — must be in the same DB transaction as
          dunning sequence stop + HITL bulk cancel.
          Idempotent: mark_paid checks paid_at before writing.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.dunning
HITL:     None — repository only (HITL cancel in hitl_repo).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update

from app.infra.db.models.dunning import Invoice
from app.infra.db.repos.base_repo import TenantRepository


class InvoiceRepository(TenantRepository):
    async def get_by_id(self, invoice_id: str) -> Invoice | None:
        result = await self._session.execute(
            select(Invoice).where(
                self._tenant_filter(Invoice),
                Invoice.invoice_id == invoice_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def list_all(
        self,
        limit: int = 100,
        direction: str | None = None,
        invoice_type: str | None = None,
        status: str | None = None,
    ) -> list[Invoice]:
        q = select(Invoice).where(self._tenant_filter(Invoice))
        if direction:
            q = q.where(Invoice.direction == direction)
        if invoice_type:
            q = q.where(Invoice.invoice_type == invoice_type)
        if status:
            q = q.where(Invoice.status == status)
        q = q.order_by(Invoice.due_date.asc()).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Track 1: payables due in exactly N days ────────────────────────────────

    async def list_unpaid_payables_by_due_date(self, due_date: date) -> list[Invoice]:
        """Return unpaid payable invoices whose due_date is exactly the given date."""
        result = await self._session.execute(
            select(Invoice).where(
                self._tenant_filter(Invoice),
                Invoice.direction == "payable",
                Invoice.status == "unpaid",
                Invoice.due_date == due_date,
            )
        )
        return list(result.scalars().all())

    # ── Track 3: B2B receivables overdue at Day 7 / 14 / 21 ──────────────────

    async def list_overdue_b2b_receivables(self, today: date) -> list[Invoice]:
        """Unpaid B2B receivables whose due_date was exactly 7, 14, or 21 days ago."""
        trigger_dates = [
            today - timedelta(days=7),
            today - timedelta(days=14),
            today - timedelta(days=21),
        ]
        result = await self._session.execute(
            select(Invoice).where(
                self._tenant_filter(Invoice),
                Invoice.direction == "receivable",
                Invoice.invoice_type == "b2b",
                Invoice.status == "unpaid",
                Invoice.due_date.in_(trigger_dates),
            )
        )
        return list(result.scalars().all())

    # ── Track 4: B2C overdue at Day 3 / 7 / 14 from invoice_date ─────────────

    async def list_overdue_b2c(self, today: date) -> list[Invoice]:
        """Unpaid B2C receivables whose invoice_date was exactly 3, 7, or 14 days ago."""
        trigger_dates = [
            today - timedelta(days=3),
            today - timedelta(days=7),
            today - timedelta(days=14),
        ]
        result = await self._session.execute(
            select(Invoice).where(
                self._tenant_filter(Invoice),
                Invoice.direction == "receivable",
                Invoice.invoice_type == "b2c",
                Invoice.status == "unpaid",
                Invoice.invoice_date.in_(trigger_dates),
            )
        )
        return list(result.scalars().all())

    # ── Payment ────────────────────────────────────────────────────────────────

    async def mark_paid(
        self,
        invoice_id: str,
        paid_at: datetime | None = None,
    ) -> Invoice | None:
        """Mark invoice as paid. Idempotent: no-op if already paid. Returns updated invoice."""
        invoice = await self.get_by_id(invoice_id)
        if invoice is None:
            return None
        if invoice.paid_at is not None:
            return invoice  # already paid — idempotent

        now = paid_at or datetime.now(UTC)
        await self._session.execute(
            update(Invoice)
            .where(
                self._tenant_filter(Invoice),
                Invoice.invoice_id == invoice_id,
            )
            .values(status="paid", paid_at=now)
        )
        invoice.status = "paid"
        invoice.paid_at = now
        return invoice

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_aging_buckets(self, today: date) -> dict[str, Any]:
        """
        Return aging report: total amount due per bucket.
        Buckets: current (not yet due), 1-30, 31-60, 61-90, over_90.
        Only counts unpaid receivables.
        """
        invoices = await self.list_all(limit=10000, direction="receivable", status="unpaid")

        buckets: dict[str, float] = {
            "current": 0.0,
            "days_1_30": 0.0,
            "days_31_60": 0.0,
            "days_61_90": 0.0,
            "over_90": 0.0,
        }
        for inv in invoices:
            days_overdue = (today - inv.due_date).days
            amount = float(inv.amount_due) if isinstance(inv.amount_due, Decimal) else inv.amount_due
            if days_overdue <= 0:
                buckets["current"] += amount
            elif days_overdue <= 30:
                buckets["days_1_30"] += amount
            elif days_overdue <= 60:
                buckets["days_31_60"] += amount
            elif days_overdue <= 90:
                buckets["days_61_90"] += amount
            else:
                buckets["over_90"] += amount

        return {k: round(v, 2) for k, v in buckets.items()}
