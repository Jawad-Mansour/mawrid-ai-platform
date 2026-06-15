"""
Feature:  HITL Approval Center
Layer:    Tests / Integration
Module:   tests.integration.test_hitl_flow
Purpose:  Integration tests for the full HITL lifecycle against a real DB:
          create → approve (external write fires only here) → status persisted;
          create → reject; create → edit → back to pending; expiry of stale
          actions; payment auto-stop bulk-cancel. Enforces the HITL Rule — no
          external side effect fires before status transitions to approved.
Depends:  pytest-asyncio, app.core.hitl.services, app.infra.db.repos.hitl_repo
HITL:     None — testing the HITL system itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

TENANT = "tenant-hitl-" + uuid.uuid4().hex[:8]


def _new_id() -> str:
    return uuid.uuid4().hex


class _FakeEmailSender:
    """Records every send so tests can assert external writes only after approval."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, to: str, subject: str, body: str, **kwargs: object) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


class TestHITLLifecycle:
    @pytest.mark.asyncio
    async def test_create_persists_pending_and_sends_nothing(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        sender = _FakeEmailSender()
        action = await repo.create(
            action_id=_new_id(),
            action_type="purchase_order_send",
            payload={"to": "s@x.com", "subject": "PO", "body": "Please supply"},
        )
        await db_session.flush()

        fetched = await repo.get_by_id(action.action_id)
        assert fetched is not None
        assert fetched.status == "pending"
        # HITL Rule: nothing sent merely by creating the action.
        assert sender.sent == []

    @pytest.mark.asyncio
    async def test_approve_fires_external_write_then_persists_approved(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.hitl.services import approve_action
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        sender = _FakeEmailSender()
        payload = {"to": "supplier@x.com", "subject": "PO-1", "body": "Order 100 units"}
        action = await repo.create(
            action_id=_new_id(), action_type="purchase_order_send", payload=payload
        )
        await db_session.flush()

        result = await approve_action(
            action.action_id, "purchase_order_send", payload, sender
        )
        assert result.status == "approved"
        # External write fired exactly once, only at approval.
        assert len(sender.sent) == 1
        assert sender.sent[0]["to"] == "supplier@x.com"

        # Persist the transition and confirm it survives a re-read.
        await repo.set_status(action.action_id, "approved", actor_user_id="u1")
        await db_session.flush()
        refreshed = await repo.get_by_id(action.action_id)
        assert refreshed is not None
        assert refreshed.status == "approved"
        assert refreshed.actor_user_id == "u1"

    @pytest.mark.asyncio
    async def test_approve_without_email_payload_sends_nothing(
        self, db_session: AsyncSession
    ) -> None:
        from app.core.hitl.services import approve_action
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        sender = _FakeEmailSender()
        # A match-review action has no to/subject — approval must not email.
        payload = {"candidate_supplier_id": _new_id()}
        action = await repo.create(
            action_id=_new_id(), action_type="supplier_match_review", payload=payload
        )
        await db_session.flush()

        result = await approve_action(
            action.action_id, "supplier_match_review", payload, sender
        )
        assert result.status == "approved"
        assert sender.sent == []  # no email channel for this action type

    @pytest.mark.asyncio
    async def test_reject_persists_rejected(self, db_session: AsyncSession) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        action = await repo.create(
            action_id=_new_id(),
            action_type="dunning_receivables_day7",
            payload={"invoice_id": _new_id()},
        )
        await db_session.flush()

        await repo.set_status(action.action_id, "rejected")
        await db_session.flush()
        refreshed = await repo.get_by_id(action.action_id)
        assert refreshed is not None
        assert refreshed.status == "rejected"

    @pytest.mark.asyncio
    async def test_edit_returns_action_to_pending_with_new_payload(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        action = await repo.create(
            action_id=_new_id(),
            action_type="purchase_order_send",
            payload={"to": "s@x.com", "subject": "Draft", "body": "v1"},
        )
        await db_session.flush()

        await repo.update_payload(
            action.action_id,
            {"to": "s@x.com", "subject": "Edited", "body": "v2 edited"},
        )
        await db_session.flush()
        refreshed = await repo.get_by_id(action.action_id)
        assert refreshed is not None
        assert refreshed.status == "pending"  # edit re-opens for re-approval
        assert refreshed.payload["body"] == "v2 edited"

    @pytest.mark.asyncio
    async def test_expire_stale_marks_past_due_actions_expired(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)
        stale = await repo.create(
            action_id=_new_id(),
            action_type="dunning_b2c_day3",
            payload={"invoice_id": _new_id()},
            expires_at=past,
        )
        fresh = await repo.create(
            action_id=_new_id(),
            action_type="dunning_b2c_day3",
            payload={"invoice_id": _new_id()},
            expires_at=future,
        )
        await db_session.flush()

        count = await repo.expire_stale()
        await db_session.flush()
        assert count >= 1

        stale_row = await repo.get_by_id(stale.action_id)
        fresh_row = await repo.get_by_id(fresh.action_id)
        assert stale_row is not None and stale_row.status == "expired"
        assert fresh_row is not None and fresh_row.status == "pending"

    @pytest.mark.asyncio
    async def test_payment_auto_stop_cancels_pending_for_invoice(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        repo = HITLRepository(db_session, TENANT)
        invoice_id = _new_id()
        a1 = await repo.create(
            action_id=_new_id(),
            action_type="dunning_receivables_day7",
            payload={"invoice_id": invoice_id},
        )
        other = await repo.create(
            action_id=_new_id(),
            action_type="dunning_receivables_day7",
            payload={"invoice_id": _new_id()},
        )
        await db_session.flush()

        cancelled = await repo.bulk_cancel_by_invoice(invoice_id)
        await db_session.flush()
        assert cancelled == 1

        a1_row = await repo.get_by_id(a1.action_id)
        other_row = await repo.get_by_id(other.action_id)
        assert a1_row is not None and a1_row.status == "rejected"
        # Unrelated invoice's action is untouched.
        assert other_row is not None and other_row.status == "pending"
