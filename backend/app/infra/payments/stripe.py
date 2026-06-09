"""
Feature:  Customer-Facing Storefront
Layer:    Infra / Payments
Module:   app.infra.payments.stripe
Purpose:  Stripe PaymentGateway implementation. Webhook verification uses
          stripe.Webhook.construct_event (HMAC-SHA256 under the hood).
          Satisfies PaymentGateway Protocol from app.infra.payments.protocol.
Depends:  stripe, app.infra.payments.protocol
HITL:     None — payment infrastructure only.
"""
