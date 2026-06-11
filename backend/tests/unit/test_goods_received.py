"""
Feature:  Procurement — Goods Received
Layer:    Test / Unit
Module:   tests.unit.test_goods_received
Purpose:  Unit tests for the goods-received flow. Verifies: lifecycle transition
          to in_stock, product remains unpublished until importer explicitly
          publishes, damage and discrepancy flags set correctly.
          No auto-HITL on goods received — dispute is importer-initiated via UI.
Depends:  app.core.procurement.services
HITL:     None at goods-received stage (dispute_letter is initiated manually)
"""

from __future__ import annotations

import pytest


class TestGoodsReceived:
    @pytest.mark.asyncio
    async def test_shipment_transitions_to_in_stock(self) -> None:
        """Confirming goods received must set status to in_stock."""
        from app.core.procurement.services import confirm_goods_received

        result = await confirm_goods_received(
            tenant_id="tenant1",
            shipment_id="ship_001",
            received_items=[{"product_id": "p1", "quantity_received": 10}],
        )
        assert result.status == "in_stock"

    @pytest.mark.asyncio
    async def test_product_not_published_after_receiving(self) -> None:
        """Receiving goods must not auto-publish — importer must act explicitly."""
        from app.core.procurement.services import confirm_goods_received

        result = await confirm_goods_received(
            tenant_id="tenant1",
            shipment_id="ship_002",
            received_items=[{"product_id": "p2", "quantity_received": 5}],
        )
        assert result.storefront_status == "not_published"

    @pytest.mark.asyncio
    async def test_damage_flag_set_when_damaged_qty_positive(self) -> None:
        """damage_detected flag must be True when any item has qty_damaged > 0."""
        from app.core.procurement.services import confirm_goods_received

        result = await confirm_goods_received(
            tenant_id="tenant1",
            shipment_id="ship_003",
            received_items=[{"product_id": "p3", "quantity_received": 10, "qty_damaged": 2}],
        )
        assert result.damage_detected is True

    @pytest.mark.asyncio
    async def test_no_damage_flag_when_no_damaged_items(self) -> None:
        """damage_detected must be False when all items arrived intact."""
        from app.core.procurement.services import confirm_goods_received

        result = await confirm_goods_received(
            tenant_id="tenant1",
            shipment_id="ship_004",
            received_items=[{"product_id": "p4", "quantity_received": 5, "qty_damaged": 0}],
        )
        assert result.damage_detected is False

    def test_stock_delta_subtracts_damaged(self) -> None:
        """Net stock added = qty_received - qty_damaged."""
        from app.core.procurement.services import ReceiveItem, stock_delta

        received = [
            ReceiveItem(product_id="p1", qty_received=10, qty_damaged=2),
            ReceiveItem(product_id="p2", qty_received=5, qty_damaged=0),
        ]
        delta = stock_delta(received)
        assert delta["p1"] == 8
        assert delta["p2"] == 5

    def test_stock_delta_never_negative(self) -> None:
        """Net qty can't go negative even if damaged > received (data entry error)."""
        from app.core.procurement.services import ReceiveItem, stock_delta

        received = [ReceiveItem(product_id="p1", qty_received=2, qty_damaged=5)]
        assert stock_delta(received)["p1"] == 0
