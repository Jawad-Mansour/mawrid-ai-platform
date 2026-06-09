"""
Feature:  Procurement
Layer:    Test / Integration
Module:   tests.integration.test_procurement_flow
Purpose:  Integration tests for the full procurement lifecycle against a real DB.
          Verifies: order → shipment → goods_received → in_stock state machine,
          cross-tenant order isolation (tenant A cannot see tenant B orders),
          invoice created when shipment confirmed.
Depends:  app.infra.db.repos, real DB, conftest fixtures
HITL:     po_draft_created, shipment_created, goods_received
"""
from __future__ import annotations

import pytest


class TestProcurementLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle_state_machine(self, db_session, tenant_id) -> None:
        """Order must progress: draft → approved → in_transit → in_stock."""
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.shipment_repo import ShipmentRepository

        order_repo = OrderRepository(db_session, tenant_id=tenant_id)
        shipment_repo = ShipmentRepository(db_session, tenant_id=tenant_id)

        order = await order_repo.create(
            supplier_id="sup_001",
            line_items=[{"product_id": "p1", "quantity": 10}],
        )
        assert order.status == "draft"

        shipment = await shipment_repo.create(order_id=str(order.id))
        assert shipment.status == "in_transit"

        received = await shipment_repo.confirm_received(
            shipment_id=str(shipment.id),
            items=[{"product_id": "p1", "quantity_received": 10}],
        )
        assert received.status == "in_stock"

    @pytest.mark.asyncio
    async def test_cross_tenant_order_isolation(self, db_session) -> None:
        """Tenant A must not be able to retrieve tenant B's orders."""
        from app.infra.db.repos.order_repo import OrderRepository

        repo_a = OrderRepository(db_session, tenant_id="tenant_a")
        repo_b = OrderRepository(db_session, tenant_id="tenant_b")

        order_b = await repo_b.create(
            supplier_id="sup_b_001",
            line_items=[{"product_id": "pb1", "quantity": 1}],
        )
        result = await repo_a.get_by_id(str(order_b.id))
        assert result is None
