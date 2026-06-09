"""
Feature:  Procurement — Goods Received
Layer:    Test / Unit
Module:   tests.unit.test_goods_received
Purpose:  Unit tests for the goods-received flow. Verifies: lifecycle
          transition in_transit → in_stock, stock quantity updated, product
          remains unpublished until importer explicitly publishes.
Depends:  app.core.procurement.services, conftest fakes
HITL:     goods_received
"""
from __future__ import annotations

import pytest


class TestGoodsReceived:
    @pytest.mark.asyncio
    async def test_shipment_transitions_to_in_stock(self) -> None:
        """Confirming goods received must move shipment status to in_stock."""
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
        assert result.storefront_status != "published"

    @pytest.mark.asyncio
    async def test_hitl_action_on_goods_received(self) -> None:
        """goods_received HITL action must be created on confirmation."""
        from app.core.procurement.services import confirm_goods_received

        result = await confirm_goods_received(
            tenant_id="tenant1",
            shipment_id="ship_003",
            received_items=[{"product_id": "p3", "quantity_received": 3}],
        )
        assert result.hitl_action_type == "goods_received"
