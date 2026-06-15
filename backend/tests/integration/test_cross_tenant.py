"""
Feature:  Multi-Tenant Isolation
Layer:    Tests / Integration
Module:   tests.integration.test_cross_tenant
Purpose:  Cross-tenant red-team — 15 attack vectors. Verifies tenant A can never
          read, modify, delete, or otherwise reach tenant B's data through any
          repository or the pgvector search layer. Runs against real PostgreSQL.
          ANY successful cross-tenant access = CI hard fail (Gate 5).
          Each vector seeds rows for BOTH tenants in the same transaction, then
          drives a tenant-A-scoped accessor and asserts tenant B's data is
          invisible / immutable.
Depends:  real Postgres via DATABASE_URL, app.infra.db repos + pgvector
HITL:     None — testing isolation itself.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.infra.db.models.hitl import HITLAction
    from app.infra.db.models.product import Product

pytestmark = pytest.mark.integration

TENANT_A = "tenant-A-" + uuid.uuid4().hex[:8]
TENANT_B = "tenant-B-" + uuid.uuid4().hex[:8]


def _new_id() -> str:
    return uuid.uuid4().hex


# ── Helpers to seed one row per tenant ─────────────────────────────────────────


async def _make_product(
    session: AsyncSession,
    tenant: str,
    *,
    name: str = "Widget",
    enrichment_status: str = "enriched",
    storefront_status: str = "published",
    barcode: str | None = None,
    storefront_qty: int = 10,
) -> Product:
    from app.core.catalog.hash import compute_product_hash
    from app.infra.db.models.product import Product
    from app.infra.db.repos.product_repo import ProductRepository

    product = Product(
        product_id=_new_id(),
        tenant_id=tenant,
        product_hash=compute_product_hash(tenant, name),
        product_name=name,
        enrichment_status=enrichment_status,
        storefront_status=storefront_status,
        barcode=barcode,
        storefront_qty=storefront_qty,
    )
    saved = await ProductRepository(session, tenant).upsert(product)
    await session.flush()
    return saved


# ── Vectors 1–6: Products ──────────────────────────────────────────────────────


class TestProductIsolation:
    @pytest.mark.asyncio
    async def test_v1_get_by_id_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        b_product = await _make_product(db_session, TENANT_B, name="B Secret Product")
        # Tenant A asks for B's product by its real id → must not see it.
        leaked = await ProductRepository(db_session, TENANT_A).get_by_id(
            b_product.product_id
        )
        assert leaked is None

    @pytest.mark.asyncio
    async def test_v2_get_by_hash_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        b_product = await _make_product(db_session, TENANT_B, name="B Hashed Product")
        leaked = await ProductRepository(db_session, TENANT_A).get_by_hash(
            b_product.product_hash
        )
        assert leaked is None

    @pytest.mark.asyncio
    async def test_v3_get_by_barcode_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        barcode = "EAN-" + uuid.uuid4().hex[:10]
        await _make_product(db_session, TENANT_B, name="B Barcoded", barcode=barcode)
        leaked = await ProductRepository(db_session, TENANT_A).get_by_barcode(barcode)
        assert leaked is None

    @pytest.mark.asyncio
    async def test_v4_list_all_excludes_other_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        a_product = await _make_product(db_session, TENANT_A, name="A Listed")
        b_product = await _make_product(db_session, TENANT_B, name="B Listed")
        a_ids = {
            p.product_id for p in await ProductRepository(db_session, TENANT_A).list_all()
        }
        assert a_product.product_id in a_ids
        assert b_product.product_id not in a_ids

    @pytest.mark.asyncio
    async def test_v5_status_update_cannot_touch_other_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        b_product = await _make_product(
            db_session, TENANT_B, name="B Unpublishable", storefront_status="published"
        )
        # Tenant A tries to unpublish B's product.
        await ProductRepository(db_session, TENANT_A).set_storefront_status(
            b_product.product_id, "not_published"
        )
        await db_session.flush()
        # B's product is unchanged when read by B.
        still = await ProductRepository(db_session, TENANT_B).get_by_id(
            b_product.product_id
        )
        assert still is not None
        assert still.storefront_status == "published"

    @pytest.mark.asyncio
    async def test_v6_decrement_qty_cannot_affect_other_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.product_repo import ProductRepository

        b_product = await _make_product(
            db_session, TENANT_B, name="B Stock", storefront_qty=10
        )
        ok = await ProductRepository(db_session, TENANT_A).decrement_storefront_qty(
            b_product.product_id, 5
        )
        assert ok is False  # A cannot decrement B's stock
        await db_session.flush()
        still = await ProductRepository(db_session, TENANT_B).get_by_id(
            b_product.product_id
        )
        assert still is not None
        assert still.storefront_qty == 10  # noqa: PLR2004


# ── Vectors 7–10: HITL actions ─────────────────────────────────────────────────


class TestHITLIsolation:
    async def _make_hitl(
        self, session: AsyncSession, tenant: str, invoice_id: str = ""
    ) -> HITLAction:
        from app.infra.db.repos.hitl_repo import HITLRepository

        action = await HITLRepository(session, tenant).create(
            action_id=_new_id(),
            action_type="purchase_order_send",
            payload={"invoice_id": invoice_id or _new_id(), "tenant_marker": tenant},
        )
        await session.flush()
        return action

    @pytest.mark.asyncio
    async def test_v7_get_by_id_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        b_action = await self._make_hitl(db_session, TENANT_B)
        leaked = await HITLRepository(db_session, TENANT_A).get_by_id(b_action.action_id)
        assert leaked is None

    @pytest.mark.asyncio
    async def test_v8_list_pending_excludes_other_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        b_action = await self._make_hitl(db_session, TENANT_B)
        a_pending = await HITLRepository(db_session, TENANT_A).list_pending()
        assert b_action.action_id not in {a.action_id for a in a_pending}

    @pytest.mark.asyncio
    async def test_v9_set_status_cannot_touch_other_tenant(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        b_action = await self._make_hitl(db_session, TENANT_B)
        await HITLRepository(db_session, TENANT_A).set_status(
            b_action.action_id, "approved"
        )
        await db_session.flush()
        still = await HITLRepository(db_session, TENANT_B).get_by_id(b_action.action_id)
        assert still is not None
        assert still.status == "pending"  # A's approve did nothing

    @pytest.mark.asyncio
    async def test_v10_bulk_cancel_by_invoice_is_tenant_scoped(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.hitl_repo import HITLRepository

        shared_invoice = _new_id()
        b_action = await self._make_hitl(
            db_session, TENANT_B, invoice_id=shared_invoice
        )
        # A cancels by the SAME invoice id — must not reach B's action.
        cancelled = await HITLRepository(db_session, TENANT_A).bulk_cancel_by_invoice(
            shared_invoice
        )
        assert cancelled == 0
        await db_session.flush()
        still = await HITLRepository(db_session, TENANT_B).get_by_id(b_action.action_id)
        assert still is not None
        assert still.status == "pending"


# ── Vectors 11–13: Suppliers, Customers, Invoices ──────────────────────────────


class TestDomainEntityIsolation:
    @pytest.mark.asyncio
    async def test_v11_supplier_get_by_id_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.supplier_repo import SupplierRepository

        b_supplier = await SupplierRepository(db_session, TENANT_B).create(
            supplier_id=_new_id(), name="B Supplier", email="b@s.com"
        )
        await db_session.flush()
        leaked = await SupplierRepository(db_session, TENANT_A).get_by_id(
            b_supplier.supplier_id
        )
        assert leaked is None

    @pytest.mark.asyncio
    async def test_v12_customer_get_by_id_and_email_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.models.customer import Customer
        from app.infra.db.repos.customer_repo import CustomerRepository

        email = f"b-{uuid.uuid4().hex[:8]}@cust.com"
        b_customer = Customer(
            customer_id=_new_id(),
            tenant_id=TENANT_B,
            name="B Customer",
            customer_type="b2c",
            email=email,
        )
        await CustomerRepository(db_session, TENANT_B).create(b_customer)
        await db_session.flush()
        repo_a = CustomerRepository(db_session, TENANT_A)
        assert await repo_a.get_by_id(b_customer.customer_id) is None
        assert await repo_a.get_by_email(email) is None

    @pytest.mark.asyncio
    async def test_v13_invoice_get_by_id_cross_tenant_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.models.dunning import Invoice
        from app.infra.db.repos.invoice_repo import InvoiceRepository

        today = date.today()
        b_invoice = Invoice(
            invoice_id=_new_id(),
            tenant_id=TENANT_B,
            direction="receivable",
            invoice_type="b2b",
            amount_due=1000.0,
            invoice_date=today,
            due_date=today,
        )
        await InvoiceRepository(db_session, TENANT_B).create(b_invoice)
        await db_session.flush()
        leaked = await InvoiceRepository(db_session, TENANT_A).get_by_id(
            b_invoice.invoice_id
        )
        assert leaked is None


# ── Vectors 14–15: Vector search (Layer 3) + Outbox ────────────────────────────


class TestVectorAndOutboxIsolation:
    @pytest.mark.asyncio
    async def test_v14_pgvector_search_only_returns_own_tenant_chunks(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.models.product_chunks import ProductChunk
        from app.infra.vector.pgvector import search_chunks

        a_product = await _make_product(db_session, TENANT_A, name="A Vec Product")
        b_product = await _make_product(db_session, TENANT_B, name="B Vec Product")

        vec = [0.05] * 1536
        for tenant, product in ((TENANT_A, a_product), (TENANT_B, b_product)):
            db_session.add(
                ProductChunk(
                    chunk_id=_new_id(),
                    tenant_id=tenant,
                    product_id=product.product_id,
                    chunk_type="child",
                    parent_chunk_id=None,
                    chunk_index=0,
                    chunk_text=f"{tenant} chunk text",
                    embedding=vec,
                )
            )
        await db_session.flush()

        hits = await search_chunks(
            db_session, TENANT_A, query_embedding=vec, top_k=20, scope="all"
        )
        returned_products = {h.product_id for h in hits}
        assert b_product.product_id not in returned_products

    @pytest.mark.asyncio
    async def test_v15_outbox_pending_batch_is_tenant_scoped(
        self, db_session: AsyncSession
    ) -> None:
        from app.infra.db.repos.outbox_repo import OutboxRepository

        b_event = await OutboxRepository(db_session, TENANT_B).create(
            event_type="embedding_requested",
            payload={"product_id": _new_id(), "tenant_id": TENANT_B},
        )
        await db_session.flush()
        a_batch = await OutboxRepository(db_session, TENANT_A).get_pending_batch()
        assert b_event.event_id not in {e.event_id for e in a_batch}
