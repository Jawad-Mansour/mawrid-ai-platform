"""
Feature:  Payment Webhooks & n8n Event Callbacks (cross-cutting)
Layer:    Tests / Unit
Module:   tests.unit.test_webhooks
Purpose:  Unit tests for backend webhook endpoints (Stripe HMAC, n8n service
          token auth, enrichment_done, stock_threshold, order_confirmed).
          All DB calls mocked — no Docker required.
Depends:  app.api.webhooks, fastapi.testclient
HITL:     None.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.deps import get_session
from app.api.webhooks import (
    _verify_service_token,
    _verify_stripe_signature,
    router,
)
from app.core.config import get_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── App fixture ──────────────────────────────────────────────────────────────


def _mock_session_override() -> AsyncSession:
    """Override DB session — returns a MagicMock for unit tests."""
    result: AsyncSession = MagicMock(spec=AsyncSession)
    return result


@pytest.fixture()
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1")
    # Override DB session so unit tests don't need a real DB
    _app.dependency_overrides[get_session] = _mock_session_override
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── _verify_service_token ─────────────────────────────────────────────────────


class TestVerifyServiceToken:
    def test_valid_token_passes(self) -> None:
        settings = get_settings()
        with patch("app.api.webhooks.get_settings", return_value=settings):
            _verify_service_token(settings.n8n_service_token)  # must not raise

    def test_none_raises(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _verify_service_token(None)
        assert exc_info.value.status_code == 401

    def test_wrong_token_raises(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _verify_service_token("wrong-token")
        assert exc_info.value.status_code == 401


# ── _verify_stripe_signature ──────────────────────────────────────────────────


class TestVerifyStripeSignature:
    def _make_sig_header(self, payload: bytes, secret: str, ts: int | None = None) -> str:
        t = ts if ts is not None else int(time.time())
        signed = f"{t}.".encode() + payload
        sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return f"t={t},v1={sig}"

    def test_valid_signature_passes(self) -> None:
        payload = b'{"type":"payment_intent.succeeded"}'
        secret = "whsec_test"
        sig = self._make_sig_header(payload, secret)
        _verify_stripe_signature(payload, sig, secret)  # must not raise

    def test_wrong_secret_raises(self) -> None:
        from fastapi import HTTPException

        payload = b'{"type":"test"}'
        sig = self._make_sig_header(payload, "real-secret")
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(payload, sig, "wrong-secret")
        assert exc_info.value.status_code == 400

    def test_replayed_timestamp_raises(self) -> None:
        from fastapi import HTTPException

        payload = b'{"type":"test"}'
        secret = "whsec_test"
        old_ts = int(time.time()) - 400  # 400s ago > 300s tolerance
        sig = self._make_sig_header(payload, secret, ts=old_ts)
        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(payload, sig, secret)
        assert exc_info.value.status_code == 400

    def test_malformed_header_raises(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _verify_stripe_signature(b"payload", "not-valid-format", "secret")
        assert exc_info.value.status_code == 400


# ── n8n/enrichment_done ───────────────────────────────────────────────────────


class TestEnrichmentDoneEndpoint:
    _url = "/api/v1/webhooks/n8n/enrichment_done"

    def test_valid_request_returns_ok(self, client: TestClient) -> None:
        settings = get_settings()
        resp = client.post(
            self._url,
            json={"tenant_id": "t1", "document_id": "doc123", "product_count": 5},
            headers={"X-N8N-Service-Token": settings.n8n_service_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "doc123" in data["detail"]

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            self._url,
            json={"tenant_id": "t1", "document_id": "doc123", "product_count": 5},
        )
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            self._url,
            json={"tenant_id": "t1", "document_id": "doc123", "product_count": 5},
            headers={"X-N8N-Service-Token": "bad-token"},
        )
        assert resp.status_code == 401


# ── n8n/stock_threshold ───────────────────────────────────────────────────────


class TestStockThresholdEndpoint:
    _url = "/api/v1/webhooks/n8n/stock_threshold"

    def test_valid_request_returns_202(self, client: TestClient) -> None:
        settings = get_settings()
        with patch(
            "app.core.suppliers.services.trigger_reorder_check",
            new_callable=AsyncMock,
        ):
            resp = client.post(
                self._url,
                json={
                    "tenant_id": "t1",
                    "product_id": "p1",
                    "product_name": "Widget",
                    "qty_in_stock": 2,
                    "reorder_threshold": 5,
                },
                headers={"X-N8N-Service-Token": settings.n8n_service_token},
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            self._url,
            json={
                "tenant_id": "t1",
                "product_id": "p1",
                "product_name": "Widget",
                "qty_in_stock": 2,
                "reorder_threshold": 5,
            },
        )
        assert resp.status_code == 401


# ── n8n/order_confirmed ───────────────────────────────────────────────────────


class TestOrderConfirmedEndpoint:
    _url = "/api/v1/webhooks/n8n/order_confirmed"

    def test_valid_request_returns_202(self, client: TestClient) -> None:
        settings = get_settings()
        resp = client.post(
            self._url,
            json={
                "tenant_id": "t1",
                "order_id": "ord123",
                "invoice_id": "inv456",
                "consumer_email": "consumer@example.com",
                "total_amount": 199.99,
            },
            headers={"X-N8N-Service-Token": settings.n8n_service_token},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "accepted"

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            self._url,
            json={
                "tenant_id": "t1",
                "order_id": "ord123",
                "invoice_id": "inv456",
                "consumer_email": "consumer@example.com",
                "total_amount": 199.99,
            },
        )
        assert resp.status_code == 401


# ── Stripe webhook ────────────────────────────────────────────────────────────


class TestStripeWebhook:
    _url = "/api/v1/webhooks/stripe"

    def _stripe_payload(self, tenant_id: str = "t1", invoice_id: str = "inv1") -> dict[str, Any]:
        return {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "amount": 19999,
                    "metadata": {"tenant_id": tenant_id, "invoice_id": invoice_id},
                }
            },
        }

    def test_non_payment_event_is_ignored(self, client: TestClient) -> None:
        payload = json.dumps({"type": "customer.created"}).encode()
        resp = client.post(
            self._url,
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_missing_tenant_id_returns_422(self, client: TestClient) -> None:
        bad_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"metadata": {}}},
        }
        resp = client.post(
            self._url,
            content=json.dumps(bad_event).encode(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_invalid_json_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            self._url,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_payment_processes_when_invoice_unpaid(self, client: TestClient) -> None:
        payload = json.dumps(self._stripe_payload()).encode()
        mock_invoice = MagicMock()
        mock_invoice.paid_at = None
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_invoice)
        mock_repo.mark_paid = AsyncMock()

        with (
            patch(
                "app.infra.db.repos.invoice_repo.InvoiceRepository",
                return_value=mock_repo,
            ),
            patch("app.core.dunning.services.auto_stop_on_payment", new_callable=AsyncMock),
            patch("app.infra.secrets.vault.get_secrets", side_effect=Exception("vault down")),
        ):
            resp = client.post(
                self._url,
                content=payload,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── n8n client ────────────────────────────────────────────────────────────────


class TestN8nClient:
    @pytest.mark.asyncio
    async def test_fire_event_succeeds(self) -> None:
        from app.infra.n8n.client import fire_event

        with patch("app.infra.n8n.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await fire_event("test-event", {"key": "value"})
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert "test-event" in call_kwargs.args[0]

    @pytest.mark.asyncio
    async def test_fire_event_never_raises_on_network_error(self) -> None:
        from app.infra.n8n.client import fire_event

        with patch("app.infra.n8n.client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value = mock_client

            # Must not raise even when httpx fails
            await fire_event("test-event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_fire_event_logs_warning_on_4xx(self) -> None:

        from app.infra.n8n.client import fire_event

        with (
            patch("app.infra.n8n.client.httpx.AsyncClient") as mock_client_cls,
            patch("app.infra.n8n.client.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await fire_event("test-event", {})
            mock_logger.warning.assert_called_once()
