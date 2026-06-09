"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.protocol
Purpose:  PaymentGateway Protocol (structural typing). All three gateways
          (Stripe, OMT, Whish) implement this Protocol. Webhook verification
          method signature enforces HMAC-SHA256 for all gateways.
Depends:  typing_extensions
HITL:     None — protocol definition only.
"""

from typing import Any, Protocol


class PaymentGateway(Protocol):
    async def create_payment_intent(
        self, amount: float, currency: str, metadata: dict[str, Any]
    ) -> dict[str, Any]: ...
    async def verify_webhook(self, payload: bytes, signature: str, secret: str) -> bool: ...
    async def refund(self, payment_intent_id: str, amount: float) -> dict[str, Any]: ...
