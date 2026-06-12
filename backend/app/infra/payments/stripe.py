"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.stripe
Purpose:  Stripe PaymentGateway implementation. create_payment_intent uses
          asyncio.to_thread over the sync Stripe SDK (stripe>=11). Webhook
          verification delegates to stripe.Webhook.construct_event (HMAC-SHA256).
          Satisfies PaymentGateway Protocol from app.infra.payments.protocol.
Depends:  stripe, app.infra.payments.protocol
HITL:     None — payment infrastructure only.
"""

from __future__ import annotations

import asyncio
from typing import Any

import stripe as _stripe


class StripeGateway:
    """Stripe PaymentGateway implementation (satisfies Protocol)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def create_payment_intent(
        self,
        amount: float,
        currency: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a Stripe PaymentIntent. Amount is in major currency units (e.g. USD).
        Returns client_secret and payment_intent_id for the frontend to complete payment.
        """
        def _create() -> _stripe.PaymentIntent:
            return _stripe.PaymentIntent.create(
                api_key=self._api_key,
                amount=int(round(amount * 100)),  # Stripe uses minor units (cents)
                currency=currency.lower(),
                metadata=metadata,
                automatic_payment_methods={"enabled": True},
            )

        intent = await asyncio.to_thread(_create)
        return {
            "payment_intent_id": intent["id"],
            "client_secret": intent["client_secret"],
            "amount": amount,
            "currency": currency,
        }

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify Stripe-Signature header using HMAC-SHA256 (v1 scheme)."""
        try:
            _stripe.Webhook.construct_event(payload, signature, secret)  # type: ignore[no-untyped-call]
            return True
        except Exception:
            return False

    async def refund(
        self,
        payment_intent_id: str,
        amount: float,
    ) -> dict[str, Any]:
        def _refund() -> _stripe.Refund:
            return _stripe.Refund.create(
                api_key=self._api_key,
                payment_intent=payment_intent_id,
                amount=int(round(amount * 100)),
            )

        refund = await asyncio.to_thread(_refund)
        return {"refund_id": refund["id"], "status": refund["status"]}
