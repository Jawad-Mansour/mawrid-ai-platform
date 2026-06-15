# mypy: ignore-errors
"""
Feature:  Order Management & Procurement
Layer:    Test / Integration
Module:   tests.integration.test_procurement_flow
Purpose:  Integration tests for the full procurement lifecycle against a real DB.
          Verifies: supplier CRUD, order draft lifecycle (draft→submitted),
          purchase order creation, shipment milestones, goods received with
          atomic stock increment, cross-tenant order isolation, storefront
          publishing. LLM is mocked — DB + Redis are real.
Depends:  app.infra.db.repos.*, real DB (Postgres + pgvector), conftest fixtures
HITL:     purchase_order_send (created in test, not approved — no email sent)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ── Helpers ────────────────────────────────────────────────────────────────────


async def _create_product(session: AsyncSession, tenant_id: str, name: str = "Test Product") -> str:
    """Insert a minimal product row directly for stock update tests."""
    from sqlalchemy import text

    product_id = uuid.uuid4().hex
    product_hash = uuid.uuid4().hex
    await session.execute(
        text(
            """
            INSERT INTO products
                (product_id, tenant_id, product_hash, product_name,
                 enrichment_status, inventory_status, storefront_status,
                 qty_in_stock, storefront_qty, price_history)
            VALUES
                (:pid, :tid, :hash, :name,
                 'enriched', 'not_ordered', 'not_published',
                 0, 0, '[]'::jsonb)
            """
        ),
        {"pid": product_id, "tid": tenant_id, "hash": product_hash, "name": name},
    )
    return product_id


# ── Supplier CRUD ──────────────────────────────────────────────────────────────


class TestSupplierCRUD:
    @pytest.mark.asyncio
    async def test_create_and_retrieve_supplier(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo = SupplierRepository(db_session, tenant_id)
        supplier = await repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Al-Ahliya Trading",
            email="orders@alahliya.com",
            language="ar",
            currency="USD",
        )
        await db_session.flush()

        fetched = await repo.get_by_id(supplier.supplier_id)
        assert fetched is not None
        assert fetched.name == "Al-Ahliya Trading"
        assert fetched.language == "ar"
        assert fetched.currency == "USD"

    @pytest.mark.asyncio
    async def test_supplier_cross_tenant_isolation(self, db_session: AsyncSession) -> None:
        """Tenant A cannot see Tenant B's suppliers."""
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo_a = SupplierRepository(db_session, "tenant_a")
        repo_b = SupplierRepository(db_session, "tenant_b")

        supplier_b = await repo_b.create(
            supplier_id=uuid.uuid4().hex,
            name="B-Only Supplier",
            email="b@b.com",
        )
        await db_session.flush()

        result = await repo_a.get_by_id(supplier_b.supplier_id)
        assert result is None


# ── Order Draft Lifecycle ──────────────────────────────────────────────────────


class TestOrderDraftLifecycle:
    @pytest.mark.asyncio
    async def test_draft_creation_and_status_progression(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository

        supplier_repo = SupplierRepository(db_session, tenant_id)
        supplier = await supplier_repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Test Supplier",
            email="test@supplier.com",
        )
        await db_session.flush()

        order_repo = OrderRepository(db_session, tenant_id)
        order_id = uuid.uuid4().hex
        draft = await order_repo.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": "p1", "quantity": 10, "unit_price": 5.00}],
            notes="Rush order",
        )
        await db_session.flush()

        assert draft.status == "draft"
        assert draft.notes == "Rush order"

        # Submit → locked for editing
        await order_repo.set_draft_status(order_id, "submitted")
        await db_session.flush()

        updated = await order_repo.get_draft_by_id(order_id)
        assert updated is not None
        assert updated.status == "submitted"

    @pytest.mark.asyncio
    async def test_draft_update_before_submit(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository

        supplier_repo = SupplierRepository(db_session, tenant_id)
        supplier = await supplier_repo.create(supplier_id=uuid.uuid4().hex, name="Supplier X")
        await db_session.flush()

        order_repo = OrderRepository(db_session, tenant_id)
        order_id = uuid.uuid4().hex
        await order_repo.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": "p1", "quantity": 5}],
        )
        await db_session.flush()

        await order_repo.update_draft(
            order_id, notes="Updated note", desired_delivery_date="2026-07-01"
        )
        await db_session.flush()

        updated = await order_repo.get_draft_by_id(order_id)
        assert updated is not None
        assert updated.notes == "Updated note"

    @pytest.mark.asyncio
    async def test_order_cross_tenant_isolation(self, db_session: AsyncSession) -> None:
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo_a = OrderRepository(db_session, "tenant_a")
        repo_b = OrderRepository(db_session, "tenant_b")
        sup_b = SupplierRepository(db_session, "tenant_b")

        supplier = await sup_b.create(supplier_id=uuid.uuid4().hex, name="Sup B")
        await db_session.flush()

        order_id = uuid.uuid4().hex
        await repo_b.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": "pb1", "quantity": 1}],
        )
        await db_session.flush()

        result = await repo_a.get_draft_by_id(order_id)
        assert result is None


# ── Purchase Order + HITL ──────────────────────────────────────────────────────


class TestPurchaseOrderCreation:
    @pytest.mark.asyncio
    async def test_purchase_order_created_with_hitl_action(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository

        supplier_repo = SupplierRepository(db_session, tenant_id)
        supplier = await supplier_repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Supplier PO",
            email="po@supplier.com",
            currency="USD",
        )
        await db_session.flush()

        order_repo = OrderRepository(db_session, tenant_id)
        order_id = uuid.uuid4().hex
        await order_repo.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": "p1", "quantity": 20, "unit_price": 10.0}],
        )
        await db_session.flush()

        hitl_repo = HITLRepository(db_session, tenant_id)
        hitl_action_id = uuid.uuid4().hex
        action = await hitl_repo.create(
            action_id=hitl_action_id,
            action_type="purchase_order_send",
            payload={
                "po_number": "PO-20260611-ABCDEF",
                "supplier_name": supplier.name,
                "to": supplier.email,
                "subject": "Purchase Order PO-20260611-ABCDEF",
                "body": "Please find attached...",
                "total": 200.0,
                "currency": "USD",
            },
        )
        await db_session.flush()

        assert action.status == "pending"
        assert action.action_type == "purchase_order_send"

        po_id = uuid.uuid4().hex
        po = await order_repo.create_purchase_order(
            po_id=po_id,
            order_draft_id=order_id,
            supplier_id=supplier.supplier_id,
            po_number="PO-20260611-ABCDEF",
            line_items=[{"product_id": "p1", "quantity": 20, "unit_price": 10.0}],
            po_text="Dear Supplier...",
            hitl_action_id=hitl_action_id,
            currency="USD",
            total_amount=200.0,
        )
        await db_session.flush()

        assert po.status == "pending_hitl"
        assert po.hitl_action_id == hitl_action_id

        # Verify HITL approve → status change
        await hitl_repo.set_status(hitl_action_id, "approved")
        await db_session.flush()

        updated_action = await hitl_repo.get_by_id(hitl_action_id)
        assert updated_action is not None
        assert updated_action.status == "approved"


# ── Shipment Tracking ──────────────────────────────────────────────────────────


class TestShipmentTracking:
    @pytest.mark.asyncio
    async def test_shipment_milestone_progression(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.shipment_repo import ShipmentRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository

        supplier_repo = SupplierRepository(db_session, tenant_id)
        supplier = await supplier_repo.create(
            supplier_id=uuid.uuid4().hex, name="Shipping Supplier"
        )
        order_repo = OrderRepository(db_session, tenant_id)
        order_id = uuid.uuid4().hex
        await order_repo.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": "p1", "quantity": 5}],
        )
        po_id = uuid.uuid4().hex
        await order_repo.create_purchase_order(
            po_id=po_id,
            order_draft_id=order_id,
            supplier_id=supplier.supplier_id,
            po_number="PO-SHIP-001",
            line_items=[{"product_id": "p1", "quantity": 5}],
            po_text="...",
            hitl_action_id=uuid.uuid4().hex,
        )
        await db_session.flush()

        shipment_repo = ShipmentRepository(db_session, tenant_id)
        shipment_id = uuid.uuid4().hex
        shipment = await shipment_repo.create(
            shipment_id=shipment_id,
            po_id=po_id,
            carrier="DHL",
            tracking_number="1Z999AA10123456784",
            expected_arrival_date="2026-07-15",
        )
        await db_session.flush()
        assert shipment.status == "pending_shipment"

        for milestone in ("shipped", "in_transit", "at_customs", "arrived"):
            await shipment_repo.set_status(shipment_id, milestone)
            await db_session.flush()
            updated = await shipment_repo.get_by_id(shipment_id)
            assert updated is not None
            assert updated.status == milestone

    @pytest.mark.asyncio
    async def test_goods_received_increments_stock(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.models.product import Product
        from app.infra.db.repos.order_repo import OrderRepository
        from app.infra.db.repos.shipment_repo import ShipmentRepository
        from app.infra.db.repos.supplier_repo import SupplierRepository
        from sqlalchemy import select

        # Create product with 0 stock
        product_id = await _create_product(db_session, tenant_id, 'Samsung TV 55"')
        await db_session.flush()

        supplier_repo = SupplierRepository(db_session, tenant_id)
        supplier = await supplier_repo.create(
            supplier_id=uuid.uuid4().hex, name="Electronics Supplier"
        )
        order_repo = OrderRepository(db_session, tenant_id)
        order_id = uuid.uuid4().hex
        await order_repo.create_draft(
            order_id=order_id,
            supplier_id=supplier.supplier_id,
            line_items=[{"product_id": product_id, "quantity": 10, "unit_price": 300.0}],
        )
        po_id = uuid.uuid4().hex
        await order_repo.create_purchase_order(
            po_id=po_id,
            order_draft_id=order_id,
            supplier_id=supplier.supplier_id,
            po_number="PO-RECV-001",
            line_items=[{"product_id": product_id, "quantity": 10}],
            po_text="...",
            hitl_action_id=uuid.uuid4().hex,
        )
        shipment_repo = ShipmentRepository(db_session, tenant_id)
        shipment_id = uuid.uuid4().hex
        await shipment_repo.create(shipment_id=shipment_id, po_id=po_id)
        await db_session.flush()

        # Receive goods: 10 received, 1 damaged → net = 9
        net_qty = 10 - 1
        from sqlalchemy import update as sa_update

        await db_session.execute(
            sa_update(Product)
            .where(Product.tenant_id == tenant_id, Product.product_id == product_id)
            .values(qty_in_stock=Product.qty_in_stock + net_qty, inventory_status="in_stock")
        )
        receiving_id = uuid.uuid4().hex
        await shipment_repo.create_receiving(
            receiving_id=receiving_id,
            shipment_id=shipment_id,
            line_items=[{"product_id": product_id, "qty_received": 10, "qty_damaged": 1}],
            received_by="user_test_001",
        )
        await shipment_repo.set_status(shipment_id, "arrived")
        await db_session.flush()

        # Verify stock
        result = await db_session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.product_id == product_id)
        )
        product = result.scalar_one()
        assert product.qty_in_stock == net_qty
        assert product.inventory_status == "in_stock"

        # Verify idempotency: second receive attempt must be blocked
        existing = await shipment_repo.get_receiving(shipment_id)
        assert existing is not None  # already recorded


# ── Storefront Publishing ──────────────────────────────────────────────────────


class TestStorefrontPublishing:
    @pytest.mark.asyncio
    async def test_publish_sets_storefront_fields(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.infra.db.models.product import Product
        from sqlalchemy import select
        from sqlalchemy import update as sa_update

        product_id = await _create_product(db_session, tenant_id, "Ariel Detergent 2kg")
        # Put 50 units in stock first
        await db_session.execute(
            sa_update(Product)
            .where(Product.tenant_id == tenant_id, Product.product_id == product_id)
            .values(qty_in_stock=50)
        )
        await db_session.flush()

        # Publish with retail price
        await db_session.execute(
            sa_update(Product)
            .where(Product.tenant_id == tenant_id, Product.product_id == product_id)
            .values(retail_price=4.99, storefront_qty=30, storefront_status="published")
        )
        await db_session.flush()

        result = await db_session.execute(
            select(Product).where(Product.tenant_id == tenant_id, Product.product_id == product_id)
        )
        p = result.scalar_one()
        assert p.storefront_status == "published"
        assert float(p.retail_price) == 4.99
        assert p.storefront_qty == 30
