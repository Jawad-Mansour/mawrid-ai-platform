"""
Feature:  Customer-Facing Storefront
Layer:    Tests / Unit
Module:   tests.unit.test_storefront
Purpose:  Unit tests for /store endpoints: product listing, product detail,
          cart validation, checkout flow, order status, and mode gate.
          All DB calls, MinIO, and payment gateways mocked — no Docker required.
Depends:  app.api.storefront, fastapi.testclient
HITL:     None.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.deps import get_session
from app.api.storefront import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _mock_session() -> Any:
    s = MagicMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    s.flush = AsyncMock()
    return s


@pytest.fixture()
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1")
    _app.dependency_overrides[get_session] = _mock_session
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


_TENANT_HEADER = {"X-Tenant-ID": "tenant-a"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_product(
    product_id: str = "p1",
    name: str = "Widget",
    price: float = 9.99,
    storefront_qty: int = 10,
    storefront_status: str = "published",
    image_path: str | None = None,
) -> Any:
    p = MagicMock()
    p.product_id = product_id
    p.product_name = name
    p.description = "A fine widget"
    p.retail_price = price
    p.storefront_qty = storefront_qty
    p.storefront_status = storefront_status
    p.currency = "USD"
    p.image_path = image_path
    p.specifications = {"color": "red"}
    p.enrichment_source = "icecat"
    return p


def _make_tenant(mode: str = "hybrid") -> Any:
    t = MagicMock()
    t.mode = mode
    t.name = "Test Tenant"
    return t


def _make_consumer_order(order_id: str = "ord1", status: str = "pending_payment") -> Any:
    o = MagicMock()
    o.order_id = order_id
    o.customer_id = "buyer@example.com"
    o.status = status
    o.payment_gateway = "stripe"
    o.total_amount = Decimal("29.97")
    o.created_at = "2026-01-01T00:00:00"
    return o


# ── Mode gate ──────────────────────────────────────────────────────────────────


class TestModeGate:
    def test_wholesale_only_returns_403(self, client: TestClient) -> None:
        mock_product_repo = MagicMock()
        mock_product_repo.list_published = AsyncMock(return_value=[])
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant(mode="wholesale_only"))

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.get("/api/v1/store/products", headers=_TENANT_HEADER)

        assert resp.status_code == 403

    def test_missing_tenant_header_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/store/products")
        assert resp.status_code == 401

    def test_hybrid_mode_passes_gate(self, client: TestClient) -> None:
        mock_product_repo = MagicMock()
        mock_product_repo.list_published = AsyncMock(return_value=[])
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant(mode="hybrid"))

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.get("/api/v1/store/products", headers=_TENANT_HEADER)

        assert resp.status_code == 200


# ── GET /store/products ────────────────────────────────────────────────────────


class TestListPublishedProducts:
    _url = "/api/v1/store/products"

    def test_returns_published_products(self, client: TestClient) -> None:
        products = [_make_product("p1"), _make_product("p2", price=19.99, storefront_qty=0)]
        mock_product_repo = MagicMock()
        mock_product_repo.list_published = AsyncMock(return_value=products)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
            patch(
                "app.api.storefront.get_presigned_url", new_callable=AsyncMock, return_value=None
            ),
        ):
            resp = client.get(self._url, headers=_TENANT_HEADER)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["product_id"] == "p1"
        assert data[1]["storefront_qty"] == 0

    def test_returns_empty_list_when_no_published(self, client: TestClient) -> None:
        mock_product_repo = MagicMock()
        mock_product_repo.list_published = AsyncMock(return_value=[])
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.get(self._url, headers=_TENANT_HEADER)

        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /store/products/{id} ───────────────────────────────────────────────────


class TestGetProductDetail:
    _url = "/api/v1/store/products/{product_id}"

    def test_returns_product_detail(self, client: TestClient) -> None:
        product = _make_product("p1")
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
            patch(
                "app.api.storefront.get_presigned_url", new_callable=AsyncMock, return_value=None
            ),
        ):
            resp = client.get(self._url.format(product_id="p1"), headers=_TENANT_HEADER)

        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == "p1"
        assert data["specifications"] == {"color": "red"}

    def test_returns_404_for_unpublished(self, client: TestClient) -> None:
        product = _make_product("p1", storefront_status="draft")
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.get(self._url.format(product_id="p1"), headers=_TENANT_HEADER)

        assert resp.status_code == 404

    def test_returns_404_when_not_found(self, client: TestClient) -> None:
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=None)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.get(self._url.format(product_id="missing"), headers=_TENANT_HEADER)

        assert resp.status_code == 404


# ── POST /store/cart/validate ──────────────────────────────────────────────────


class TestCartValidation:
    _url = "/api/v1/store/cart/validate"

    def test_valid_cart_returns_ok(self, client: TestClient) -> None:
        product = _make_product("p1", storefront_qty=10, price=9.99)
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.post(
                self._url,
                json={"items": [{"product_id": "p1", "qty": 3}]},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_insufficient_qty_returns_error(self, client: TestClient) -> None:
        product = _make_product("p1", storefront_qty=2)
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.post(
                self._url,
                json={"items": [{"product_id": "p1", "qty": 5}]},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1

    def test_unpublished_product_returns_error(self, client: TestClient) -> None:
        product = _make_product("p1", storefront_status="draft")
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.post(
                self._url,
                json={"items": [{"product_id": "p1", "qty": 1}]},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 200
        assert resp.json()["valid"] is False


# ── POST /store/checkout ───────────────────────────────────────────────────────


class TestCheckout:
    _url = "/api/v1/store/checkout"

    _body = {
        "items": [{"product_id": "p1", "qty": 2}],
        "consumer_name": "Alice Smith",
        "consumer_email": "alice@example.com",
        "delivery_address": "123 Main St",
        "payment_method": "stripe",
        "currency": "USD",
    }

    def test_checkout_creates_order_and_returns_payment_details(self, client: TestClient) -> None:
        product = _make_product("p1", price=15.00, storefront_qty=5)
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_order_repo = MagicMock()
        mock_order_repo.create = AsyncMock(return_value=MagicMock(order_id="ord-x"))
        mock_order_repo.add_item = AsyncMock()
        mock_invoice_repo = MagicMock()
        mock_invoice_repo.create = AsyncMock()
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        mock_gateway = AsyncMock()
        mock_gateway.create_payment_intent = AsyncMock(
            return_value={"client_secret": "pi_xxx_secret_yyy", "payment_intent_id": "pi_xxx"}
        )

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.ConsumerOrderRepository", return_value=mock_order_repo),
            patch("app.api.storefront.InvoiceRepository", return_value=mock_invoice_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
            patch("app.api.storefront._get_gateway", return_value=mock_gateway),
        ):
            resp = client.post(self._url, json=self._body, headers=_TENANT_HEADER)

        assert resp.status_code == 201
        data = resp.json()
        assert "order_id" in data
        assert "invoice_id" in data
        assert data["total_amount"] == 30.0  # 2 × 15.00
        assert data["payment_method"] == "stripe"
        assert "payment_details" in data

    def test_out_of_stock_returns_409(self, client: TestClient) -> None:
        product = _make_product("p1", price=10.00, storefront_qty=1)
        mock_product_repo = MagicMock()
        mock_product_repo.get_by_id = AsyncMock(return_value=product)
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with (
            patch("app.api.storefront.ProductRepository", return_value=mock_product_repo),
            patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo),
        ):
            resp = client.post(
                self._url,
                json={**self._body, "items": [{"product_id": "p1", "qty": 5}]},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 409

    def test_empty_cart_returns_422(self, client: TestClient) -> None:
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo):
            resp = client.post(
                self._url,
                json={**self._body, "items": []},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 422

    def test_invalid_payment_method_returns_422(self, client: TestClient) -> None:
        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_by_id = AsyncMock(return_value=_make_tenant())

        with patch("app.api.storefront.TenantRepo", return_value=mock_tenant_repo):
            resp = client.post(
                self._url,
                json={**self._body, "payment_method": "bitcoin"},
                headers=_TENANT_HEADER,
            )

        assert resp.status_code == 422


# ── GET /store/orders/{order_id} ──────────────────────────────────────────────


class TestGetOrderStatus:
    _url = "/api/v1/store/orders/{order_id}"

    def test_returns_order_status(self, client: TestClient) -> None:
        order = _make_consumer_order("ord1", status="paid")
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=order)

        with patch("app.api.storefront.ConsumerOrderRepository", return_value=mock_repo):
            resp = client.get(self._url.format(order_id="ord1"), headers=_TENANT_HEADER)

        assert resp.status_code == 200
        data = resp.json()
        assert data["order_id"] == "ord1"
        assert data["status"] == "paid"

    def test_returns_404_when_not_found(self, client: TestClient) -> None:
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.api.storefront.ConsumerOrderRepository", return_value=mock_repo):
            resp = client.get(self._url.format(order_id="ghost"), headers=_TENANT_HEADER)

        assert resp.status_code == 404
