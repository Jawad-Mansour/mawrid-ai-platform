# mypy: ignore-errors
"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Test / Integration
Module:   tests.integration.test_dunning_e2e
Purpose:  Phase 6.6 integration test. Verifies all 4 dunning tracks against a
          real database: HITL creation, dunning sequence creation, idempotency
          guards, payment auto-stop atomicity, and cross-tenant isolation.
          LLM (chat_completion) is mocked. Real Postgres required (Gate 4).
Depends:  app.core.dunning.services, app.infra.db.repos.*, real DB (Postgres),
          conftest fixtures (db_session, tenant_id)
HITL:     dunning_payables_advance, dunning_disputes_on_demand,
          dunning_receivables_day7, dunning_b2c_day3
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

_MOCK_DRAFT = "Dear Supplier,\n\nThis is a payment reminder.\n\nRegards, Mawrid"


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _insert_invoice(
    session: AsyncSession,
    tenant_id: str,
    *,
    direction: str = "payable",
    invoice_type: str = "b2b",
    due_date: date | None = None,
    invoice_date: date | None = None,
    status: str = "unpaid",
    contact_email: str = "contact@test.com",
    contact_name: str = "Test Contact",
    contact_language: str = "en",
    currency: str = "USD",
    amount_due: float = 1500.00,
    customer_id: str | None = None,
    supplier_id: str | None = None,
) -> str:
    from sqlalchemy import text

    invoice_id = uuid.uuid4().hex
    today = date.today()
    due = due_date or today
    inv_date = invoice_date or today

    await session.execute(
        text(
            """
            INSERT INTO invoices (
                invoice_id, tenant_id, direction, invoice_type,
                amount_due, invoice_date, due_date, payment_terms_days,
                status, contact_email, contact_name, contact_language,
                currency, customer_id, supplier_id
            ) VALUES (
                :iid, :tid, :dir, :itype,
                :amt, :idate, :ddate, 30,
                :st, :email, :name, :lang,
                :cur, :cust, :supp
            )
            """
        ),
        {
            "iid": invoice_id,
            "tid": tenant_id,
            "dir": direction,
            "itype": invoice_type,
            "amt": amount_due,
            "idate": inv_date,
            "ddate": due,
            "st": status,
            "email": contact_email,
            "name": contact_name,
            "lang": contact_language,
            "cur": currency,
            "cust": customer_id,
            "supp": supplier_id,
        },
    )
    return invoice_id


async def _insert_supplier(session: AsyncSession, tenant_id: str) -> str:
    from sqlalchemy import text

    supplier_id = uuid.uuid4().hex
    await session.execute(
        text(
            """
            INSERT INTO suppliers (supplier_id, tenant_id, name, email, language, currency)
            VALUES (:sid, :tid, :name, :email, :lang, :cur)
            """
        ),
        {
            "sid": supplier_id,
            "tid": tenant_id,
            "name": "Test Supplier",
            "email": "supplier@test.com",
            "lang": "en",
            "cur": "USD",
        },
    )
    return supplier_id


# ── Track 1 — B2B Payables ─────────────────────────────────────────────────────


class TestTrack1Payables:
    @pytest.mark.asyncio
    async def test_hitl_created_for_invoice_due_in_3_days(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Track 1 fires for payable invoices due in exactly 3 days."""
        from app.core.dunning.services import trigger_track1
        from app.infra.db.repos.dunning_repo import DunningRepository
        from app.infra.db.repos.hitl_repo import HITLRepository

        today = date.today()
        invoice_id = await _insert_invoice(
            db_session,
            tenant_id,
            direction="payable",
            due_date=today + timedelta(days=3),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track1(db_session, tenant_id, today)

        assert len(action_ids) >= 1

        hitl_repo = HITLRepository(db_session, tenant_id)
        dunning_repo = DunningRepository(db_session, tenant_id)

        pending = await hitl_repo.list_pending()
        our_actions = [a for a in pending if a.payload.get("invoice_id") == invoice_id]
        assert len(our_actions) == 1
        assert our_actions[0].action_type == "dunning_payables_advance"
        assert our_actions[0].status == "pending"

        seq = await dunning_repo.get_active_sequence(invoice_id, "payables")
        assert seq is not None
        assert seq.track == "payables"

    @pytest.mark.asyncio
    async def test_no_email_invoice_skipped(self, db_session: AsyncSession, tenant_id: str) -> None:
        """Invoices without contact_email are silently skipped."""
        from app.core.dunning.services import trigger_track1

        today = date.today()
        await _insert_invoice(
            db_session,
            tenant_id,
            direction="payable",
            due_date=today + timedelta(days=3),
            contact_email="",
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track1(db_session, tenant_id, today)

        assert action_ids == []

    @pytest.mark.asyncio
    async def test_idempotency_trigger_twice_creates_one_sequence(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Calling trigger_track1 twice for the same invoice creates only one sequence."""
        from app.core.dunning.services import trigger_track1
        from app.infra.db.repos.dunning_repo import DunningRepository

        today = date.today()
        invoice_id = await _insert_invoice(
            db_session,
            tenant_id,
            direction="payable",
            due_date=today + timedelta(days=3),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            first = await trigger_track1(db_session, tenant_id, today)
            second = await trigger_track1(db_session, tenant_id, today)

        assert len(first) == 1
        assert second == []  # idempotent — sequence already active

        dunning_repo = DunningRepository(db_session, tenant_id)
        seq = await dunning_repo.get_active_sequence(invoice_id, "payables")
        assert seq is not None

    @pytest.mark.asyncio
    async def test_wrong_due_date_not_triggered(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Invoice due in 5 days (not 3) is not picked up by Track 1."""
        from app.core.dunning.services import trigger_track1

        today = date.today()
        await _insert_invoice(
            db_session,
            tenant_id,
            direction="payable",
            due_date=today + timedelta(days=5),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track1(db_session, tenant_id, today)

        assert action_ids == []


# ── Track 2 — B2B Disputes ─────────────────────────────────────────────────────


class TestTrack2Disputes:
    @pytest.mark.asyncio
    async def test_dispute_hitl_created(self, db_session: AsyncSession, tenant_id: str) -> None:
        """Track 2 creates a HITL action with the dispute draft."""
        from app.core.dunning.services import trigger_track2
        from app.infra.db.repos.hitl_repo import HITLRepository

        supplier_id = await _insert_supplier(db_session, tenant_id)
        invoice_id = await _insert_invoice(db_session, tenant_id, supplier_id=supplier_id)
        await db_session.flush()

        dispute_context = {
            "po_reference": "PO-2026-001",
            "shipment_id": "SHP-001",
            "dispute_type": "damaged_goods",
            "products_affected_json": '[{"sku": "ABC"}]',
            "damage_description": "30% of units arrived damaged.",
            "resolution_requested": "Credit note or replacement.",
        }

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_id = await trigger_track2(
                db_session, tenant_id, invoice_id, supplier_id, dispute_context
            )

        hitl_repo = HITLRepository(db_session, tenant_id)
        action = await hitl_repo.get_by_id(action_id)
        assert action is not None
        assert action.action_type == "dunning_disputes_on_demand"
        assert action.payload["invoice_id"] == invoice_id
        assert action.payload["dispute_type"] == "damaged_goods"
        assert action.status == "pending"

    @pytest.mark.asyncio
    async def test_supplier_no_email_raises(self, db_session: AsyncSession, tenant_id: str) -> None:
        """Supplier without email raises ValueError (caller must validate)."""
        from app.core.dunning.services import trigger_track2
        from sqlalchemy import text

        supplier_id = uuid.uuid4().hex
        await db_session.execute(
            text(
                "INSERT INTO suppliers (supplier_id, tenant_id, name, language, currency) "
                "VALUES (:sid, :tid, 'No Email', 'en', 'USD')"
            ),
            {"sid": supplier_id, "tid": tenant_id},
        )
        invoice_id = await _insert_invoice(db_session, tenant_id)
        await db_session.flush()

        with (
            patch(
                "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
            ),
            pytest.raises(ValueError, match="no email"),
        ):
            await trigger_track2(db_session, tenant_id, invoice_id, supplier_id, {})


# ── Track 3 — B2B Receivables ──────────────────────────────────────────────────


class TestTrack3Receivables:
    @pytest.mark.asyncio
    async def test_day7_hitl_created(self, db_session: AsyncSession, tenant_id: str) -> None:
        """Receivable invoice overdue by 7 days triggers Day 7 HITL."""
        from app.core.dunning.services import trigger_track3
        from app.infra.db.repos.hitl_repo import HITLRepository

        today = date.today()
        invoice_id = await _insert_invoice(
            db_session,
            tenant_id,
            direction="receivable",
            invoice_type="b2b",
            due_date=today - timedelta(days=7),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track3(db_session, tenant_id, today)

        assert len(action_ids) >= 1

        hitl_repo = HITLRepository(db_session, tenant_id)
        pending = await hitl_repo.list_pending()
        our = [a for a in pending if a.payload.get("invoice_id") == invoice_id]
        assert len(our) == 1
        assert our[0].action_type == "dunning_receivables_day7"

    @pytest.mark.asyncio
    async def test_b2b_receivable_uses_tone_classifier(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Track 3 HITL payload contains 'tone' from classifier."""
        from app.core.dunning.services import trigger_track3
        from app.infra.db.repos.hitl_repo import HITLRepository

        today = date.today()
        await _insert_invoice(
            db_session,
            tenant_id,
            direction="receivable",
            invoice_type="b2b",
            due_date=today - timedelta(days=7),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track3(db_session, tenant_id, today)

        hitl_repo = HITLRepository(db_session, tenant_id)
        action = await hitl_repo.get_by_id(action_ids[0])
        assert "tone" in action.payload
        assert action.payload["tone"] in ("gentle", "neutral", "firm")


# ── Track 4 — B2C Collections ──────────────────────────────────────────────────


class TestTrack4B2C:
    @pytest.mark.asyncio
    async def test_day3_hitl_created(self, db_session: AsyncSession, tenant_id: str) -> None:
        """B2C invoice 3 days past invoice_date triggers Day 3 HITL."""
        from app.core.dunning.services import trigger_track4
        from app.infra.db.repos.hitl_repo import HITLRepository

        today = date.today()
        invoice_id = await _insert_invoice(
            db_session,
            tenant_id,
            direction="receivable",
            invoice_type="b2c",
            invoice_date=today - timedelta(days=3),
            due_date=today + timedelta(days=27),  # 30-day terms, so not overdue yet by due_date
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track4(db_session, tenant_id, today)

        assert len(action_ids) >= 1

        hitl_repo = HITLRepository(db_session, tenant_id)
        action = await hitl_repo.get_by_id(action_ids[0])
        assert action.action_type == "dunning_b2c_day3"
        assert action.payload["invoice_id"] == invoice_id
        assert action.payload["track"] == "b2c"

    @pytest.mark.asyncio
    async def test_b2c_idempotency(self, db_session: AsyncSession, tenant_id: str) -> None:
        """Triggering Track 4 twice for the same invoice creates only one HITL action."""
        from app.core.dunning.services import trigger_track4

        today = date.today()
        await _insert_invoice(
            db_session,
            tenant_id,
            direction="receivable",
            invoice_type="b2c",
            invoice_date=today - timedelta(days=3),
            due_date=today + timedelta(days=27),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            first = await trigger_track4(db_session, tenant_id, today)
            second = await trigger_track4(db_session, tenant_id, today)

        assert len(first) == 1
        assert second == []


# ── Payment Auto-Stop ──────────────────────────────────────────────────────────


class TestPaymentAutoStop:
    @pytest.mark.asyncio
    async def test_auto_stop_atomically_stops_sequence_and_cancels_hitl(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """
        When an invoice is paid, auto_stop_on_payment must atomically:
          1. Mark the invoice paid
          2. Stop the active dunning sequence
          3. Reject all pending HITL dunning actions
        """
        from app.core.dunning.services import auto_stop_on_payment, trigger_track1
        from app.infra.db.repos.dunning_repo import DunningRepository
        from app.infra.db.repos.hitl_repo import HITLRepository
        from app.infra.db.repos.invoice_repo import InvoiceRepository

        today = date.today()
        invoice_id = await _insert_invoice(
            db_session,
            tenant_id,
            direction="payable",
            due_date=today + timedelta(days=3),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track1(db_session, tenant_id, today)
        assert len(action_ids) == 1

        result = await auto_stop_on_payment(db_session, tenant_id, invoice_id)

        assert result["sequences_stopped"] >= 1
        assert result["hitl_cancelled"] >= 1

        invoice_repo = InvoiceRepository(db_session, tenant_id)
        invoice = await invoice_repo.get_by_id(invoice_id)
        assert invoice is not None
        assert invoice.paid_at is not None

        dunning_repo = DunningRepository(db_session, tenant_id)
        seq = await dunning_repo.get_active_sequence(invoice_id, "payables")
        assert seq is None  # stopped, no longer active

        hitl_repo = HITLRepository(db_session, tenant_id)
        action = await hitl_repo.get_by_id(action_ids[0])
        assert action.status == "rejected"

    @pytest.mark.asyncio
    async def test_auto_stop_idempotent_on_already_paid_invoice(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        """Calling auto_stop twice on the same invoice is safe."""
        from app.core.dunning.services import auto_stop_on_payment

        invoice_id = await _insert_invoice(db_session, tenant_id)
        await db_session.flush()

        result1 = await auto_stop_on_payment(db_session, tenant_id, invoice_id)
        result2 = await auto_stop_on_payment(db_session, tenant_id, invoice_id)

        # Second call: invoice already marked paid, sequences already stopped
        assert result1["sequences_stopped"] == 0  # no sequences were created
        assert result2["sequences_stopped"] == 0


# ── Cross-tenant isolation ─────────────────────────────────────────────────────


class TestDunningCrossTenantIsolation:
    @pytest.mark.asyncio
    async def test_track1_does_not_see_other_tenant_invoices(
        self, db_session: AsyncSession
    ) -> None:
        """Tenant A's trigger_track1 must not touch Tenant B's invoices."""
        from app.core.dunning.services import trigger_track1

        today = date.today()
        tenant_a = "dunning_tenant_a_" + uuid.uuid4().hex[:8]
        tenant_b = "dunning_tenant_b_" + uuid.uuid4().hex[:8]

        # Insert a qualifying invoice for tenant_b only
        await _insert_invoice(
            db_session,
            tenant_b,
            direction="payable",
            due_date=today + timedelta(days=3),
        )
        await db_session.flush()

        with patch(
            "app.core.dunning.services.chat_completion", new=AsyncMock(return_value=_MOCK_DRAFT)
        ):
            action_ids = await trigger_track1(db_session, tenant_a, today)

        # tenant_a should see zero matching invoices
        assert action_ids == []
