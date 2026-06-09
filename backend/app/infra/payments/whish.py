"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.whish
Purpose:  Whish Money PaymentGateway implementation.
          Webhook signature verified via HMAC-SHA256 before processing.
          Satisfies PaymentGateway Protocol.
Depends:  httpx, app.infra.payments.protocol
HITL:     None — payment infrastructure only.
"""
