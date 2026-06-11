"""
Feature:  Procurement — Order Draft
Layer:    Test / Unit
Module:   tests.unit.test_order_draft
Purpose:  Unit tests for the order draft flow. Verifies: draft created in 'draft'
          state (not sent), no email on draft creation, HITL is only triggered at
          Place Order (purchase_order_send) not at draft creation.
Depends:  app.core.procurement.services, conftest fakes
HITL:     purchase_order_send (triggered at place-order step, not tested here)
"""

from __future__ import annotations

from typing import Any

import pytest


class TestOrderDraft:
    @pytest.mark.asyncio
    async def test_draft_starts_in_draft_state(self, fake_email_sender: Any) -> None:
        """Order draft must start in 'draft' state — not submitted, not pending HITL."""
        from app.core.procurement.services import create_order_draft

        result = await create_order_draft(
            tenant_id="tenant1",
            supplier_id="sup_001",
            line_items=[{"product_id": "p1", "quantity": 10}],
            email_sender=fake_email_sender,
        )
        assert result.status == "draft"

    @pytest.mark.asyncio
    async def test_no_email_sent_on_draft_creation(self, fake_email_sender: Any) -> None:
        """No email is sent when creating a draft — HITL must be approved first."""
        from app.core.procurement.services import create_order_draft

        result = await create_order_draft(
            tenant_id="tenant1",
            supplier_id="sup_001",
            line_items=[{"product_id": "p1", "quantity": 5}],
            email_sender=fake_email_sender,
        )
        assert result.status == "draft"
        assert len(fake_email_sender.sent) == 0

    @pytest.mark.asyncio
    async def test_draft_preserves_line_items(self, fake_email_sender: Any) -> None:
        """Line items passed in must be preserved on the draft result."""
        from app.core.procurement.services import create_order_draft

        items = [{"product_id": "p1", "quantity": 3, "unit_price": 29.99}]
        result = await create_order_draft(
            tenant_id="tenant1",
            supplier_id="sup_002",
            line_items=items,
            email_sender=fake_email_sender,
        )
        assert result.supplier_id == "sup_002"
        assert result.line_items == items

    def test_compute_order_total(self) -> None:
        """Total is sum of qty * unit_price across all line items."""
        from app.core.procurement.services import compute_order_total

        items = [
            {"quantity": 10, "unit_price": 5.0},
            {"quantity": 3, "unit_price": 20.0},
        ]
        assert compute_order_total(items) == 110.0

    def test_detect_discrepancy_short_shipment(self) -> None:
        """Flag discrepancy when received qty is more than 5% short."""
        from app.core.procurement.services import ReceiveItem, detect_discrepancy

        items = [{"product_id": "p1", "quantity": 100}]
        received = [ReceiveItem(product_id="p1", qty_received=90)]  # 10% short
        assert detect_discrepancy(items, received) is True

    def test_detect_discrepancy_within_tolerance(self) -> None:
        """No discrepancy when received qty is within 5% of ordered qty."""
        from app.core.procurement.services import ReceiveItem, detect_discrepancy

        items = [{"product_id": "p1", "quantity": 100}]
        received = [ReceiveItem(product_id="p1", qty_received=96)]  # 4% short
        assert detect_discrepancy(items, received) is False
