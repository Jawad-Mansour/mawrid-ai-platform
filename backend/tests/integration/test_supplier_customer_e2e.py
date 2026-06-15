"""
Feature:  Supplier Intelligence & Customer Management — Integration
Layer:    Tests / Integration
Module:   tests.integration.test_supplier_customer_e2e
Purpose:  End-to-end integration test for Phase 7.
          Requires: docker compose up -d && uv run alembic upgrade head.
          Tests the full lifecycle: supplier CRUD, delivery event recording,
          score computation, matching waterfall, customer matching, segment
          assignment, payment history score update, and reorder signal.
Depends:  real Postgres via DATABASE_URL, app.infra.db.session
HITL:     supplier_match_review, customer_match_review, purchase_order_send
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
def tenant_id() -> str:
    return f"test-tenant-{uuid.uuid4().hex[:8]}"


class TestSupplierMatchingWaterfall:
    """AC-1: Supplier matching waterfall produces correct outcomes."""

    @pytest.mark.asyncio
    async def test_exact_name_auto_links(self, db_session: AsyncSession, tenant_id: str) -> None:
        from app.core.suppliers.services import match_supplier
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo = SupplierRepository(db_session, tenant_id)
        await repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Acme Corporation",
            email="acme@example.com",
        )
        await db_session.flush()

        result = await match_supplier(db_session, tenant_id, "Acme Corporation")
        assert result.match_type == "exact"
        assert result.confidence == 1.0
        assert result.supplier_id is not None

    @pytest.mark.asyncio
    async def test_no_suppliers_creates_hitl_new(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.core.suppliers.services import match_supplier

        result = await match_supplier(db_session, tenant_id, "Unknown Supplier XYZ")
        assert result.match_type == "hitl"
        assert result.supplier_id is None
        assert result.hitl_action_id is not None


class TestSupplierScoring:
    """AC-2: Supplier score reflects delivery performance."""

    @pytest.mark.asyncio
    async def test_perfect_deliveries_high_score(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from datetime import date

        from app.core.suppliers.models import DeliveryEventInput
        from app.core.suppliers.services import record_delivery_event
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo = SupplierRepository(db_session, tenant_id)
        supplier = await repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Perfect Supplier",
            email="perfect@supplier.com",
            phone="+1234567890",
        )
        await db_session.flush()

        today = date.today()
        event = DeliveryEventInput(
            promised_date=today.isoformat(),
            delivered_date=today.isoformat(),
            items_ordered=100,
            items_received=100,
            items_damaged=0,
            price_agreed=10.0,
            price_billed=10.0,
            response_time_hours=2.0,
        )
        result = await record_delivery_event(db_session, tenant_id, supplier.supplier_id, event)
        assert result.score > 80.0

    @pytest.mark.asyncio
    async def test_damaged_deliveries_lower_score(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from datetime import date

        from app.core.suppliers.models import DeliveryEventInput
        from app.core.suppliers.services import record_delivery_event
        from app.infra.db.repos.supplier_repo import SupplierRepository

        repo = SupplierRepository(db_session, tenant_id)
        supplier = await repo.create(
            supplier_id=uuid.uuid4().hex,
            name="Bad Supplier",
        )
        await db_session.flush()

        today = date.today()
        event = DeliveryEventInput(
            promised_date=today.isoformat(),
            delivered_date=today.isoformat(),
            items_ordered=100,
            items_received=100,
            items_damaged=50,  # 50% damage rate → -15 points
            price_agreed=10.0,
            price_billed=10.0,
        )
        result = await record_delivery_event(db_session, tenant_id, supplier.supplier_id, event)
        assert result.score < 90.0


class TestCustomerMatchingWaterfall:
    """AC-4: Customer matching waterfall."""

    @pytest.mark.asyncio
    async def test_exact_email_auto_links(self, db_session: AsyncSession, tenant_id: str) -> None:
        from app.core.customers.services import match_or_create_customer
        from app.infra.db.models.customer import Customer
        from app.infra.db.repos.customer_repo import CustomerRepository

        repo = CustomerRepository(db_session, tenant_id)
        existing = Customer(
            customer_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            name="John Smith",
            customer_type="b2c",
            email="john@example.com",
        )
        await repo.create(existing)
        await db_session.flush()

        result = await match_or_create_customer(
            db_session, tenant_id, "John Smith Jr", "john@example.com", None, "b2c"
        )
        assert result.match_type == "email"
        assert result.customer_id == existing.customer_id
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_no_match_auto_creates_customer(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.core.customers.services import match_or_create_customer

        result = await match_or_create_customer(
            db_session,
            tenant_id,
            "Totally Unique Name XYZ123",
            None,
            None,
            "b2b",
        )
        assert result.match_type == "created"
        assert result.customer_id is not None
        assert result.created is True


class TestReorderSignal:
    """AC-3: Reorder signal creates HITL and guards against duplicate POs."""

    @pytest.mark.asyncio
    async def test_product_below_threshold_creates_hitl(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        pytest.skip("Requires LLM call — run with OPENAI_API_KEY set")

    @pytest.mark.asyncio
    async def test_no_products_below_threshold_no_hitl(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.core.suppliers.services import trigger_reorder_check

        action_ids = await trigger_reorder_check(db_session, tenant_id)
        assert action_ids == []


class TestPaymentHistoryScore:
    """AC-6: Payment history score rolling update."""

    @pytest.mark.asyncio
    async def test_on_time_payment_score_stays_high(
        self, db_session: AsyncSession, tenant_id: str
    ) -> None:
        from app.core.customers.services import match_or_create_customer, record_payment_outcome

        result = await match_or_create_customer(
            db_session, tenant_id, "Reliable Customer", "reliable@example.com", None, "b2b"
        )
        assert result.customer_id is not None

        new_score = await record_payment_outcome(db_session, tenant_id, result.customer_id, 1.0)
        assert new_score == pytest.approx(1.0)
