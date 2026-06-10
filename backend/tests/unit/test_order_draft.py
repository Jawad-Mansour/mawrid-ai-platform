"""
Feature:  Procurement — Order Draft
Layer:    Test / Unit
Module:   tests.unit.test_order_draft
Purpose:  Unit tests for the order draft flow. Verifies: draft created in
          pending_approval state, HITL action created before any external
          write, no PO emailed without importer approval.
Depends:  app.core.procurement.services, conftest fakes
HITL:     po_draft_created
"""

from __future__ import annotations

from typing import Any

import pytest


class TestOrderDraft:
    @pytest.mark.asyncio
    async def test_draft_starts_in_pending_approval(self, fake_email_sender: Any) -> None:
        """Order draft must start in pending_approval, not sent."""
        from app.core.procurement.services import create_order_draft

        result = await create_order_draft(
            tenant_id="tenant1",
            supplier_id="sup_001",
            line_items=[{"product_id": "p1", "quantity": 10}],
            email_sender=fake_email_sender,
        )
        assert result.status == "pending_approval"
        assert len(fake_email_sender.sent) == 0

    @pytest.mark.asyncio
    async def test_hitl_action_created_on_draft(self, fake_email_sender: Any) -> None:
        """A hitl_actions record must be created when a draft is submitted."""
        from app.core.procurement.services import create_order_draft

        result = await create_order_draft(
            tenant_id="tenant1",
            supplier_id="sup_001",
            line_items=[{"product_id": "p1", "quantity": 5}],
            email_sender=fake_email_sender,
        )
        assert result.hitl_action_id is not None
        assert result.hitl_action_type == "po_draft_created"
