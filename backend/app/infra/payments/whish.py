"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.whish
Purpose:  Whish Money PaymentGateway implementation for Lebanese domestic
          payments. Initiates payment sessions via Whish REST API and verifies
          HMAC-SHA256 webhooks. Satisfies PaymentGateway Protocol.
          Whish API credentials stored in Vault at mawrid/whish (api_key, secret).
Depends:  httpx, app.infra.payments.protocol
HITL:     None — payment infrastructure only.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

_WHISH_BASE_URL = "https://api.whish.money/v1"


class WhishGateway:
    """Whish Money PaymentGateway implementation (satisfies Protocol)."""

    def __init__(self, api_key: str, webhook_secret: str) -> None:
        self._api_key = api_key
        self._webhook_secret = webhook_secret

    async def create_payment_intent(
        self,
        amount: float,
        currency: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Initiate a Whish payment session. Returns a redirect_url for the consumer
        to complete payment via the Whish app or portal.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_WHISH_BASE_URL}/checkout/create",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": round(amount, 2),
                    "currency": currency.upper(),
                    "order_ref": metadata.get("order_id", ""),
                    "description": metadata.get("description", "Mawrid order"),
                    "metadata": metadata,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        return {
            "checkout_id": data.get("checkout_id", ""),
            "redirect_url": data.get("payment_url", ""),
            "amount": amount,
            "currency": currency,
        }

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify Whish webhook HMAC-SHA256 signature."""
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def refund(
        self,
        payment_intent_id: str,
        amount: float,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_WHISH_BASE_URL}/checkout/{payment_intent_id}/refund",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"amount": round(amount, 2)},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        return {"refund_id": data.get("refund_id", ""), "status": data.get("status", "pending")}
