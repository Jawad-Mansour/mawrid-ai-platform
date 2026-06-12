"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.omt
Purpose:  OMT (Online Money Transfer) PaymentGateway implementation for
          Lebanese domestic payments. Initiates payment sessions and verifies
          HMAC-SHA256 webhooks. Satisfies PaymentGateway Protocol.
          OMT API credentials stored in Vault at mawrid/omt (api_key, secret).
Depends:  httpx, app.infra.payments.protocol
HITL:     None — payment infrastructure only.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

_OMT_BASE_URL = "https://api.omt.com.lb/v1"


class OMTGateway:
    """OMT PaymentGateway implementation (satisfies Protocol)."""

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
        Initiate an OMT payment session. Returns a redirect_url for the consumer
        to complete payment via the OMT portal.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_OMT_BASE_URL}/payments/initiate",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount": round(amount, 2),
                    "currency": currency.upper(),
                    "reference": metadata.get("order_id", ""),
                    "metadata": metadata,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        return {
            "payment_session_id": data.get("session_id", ""),
            "redirect_url": data.get("redirect_url", ""),
            "amount": amount,
            "currency": currency,
        }

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify OMT webhook HMAC-SHA256 signature."""
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def refund(
        self,
        payment_intent_id: str,
        amount: float,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_OMT_BASE_URL}/payments/{payment_intent_id}/refund",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"amount": round(amount, 2)},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        return {"refund_id": data.get("refund_id", ""), "status": data.get("status", "pending")}
