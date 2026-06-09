"""
Feature:  Customer-Facing Storefront
Layer:    Core / Service
Module:   app.core.storefront.services
Purpose:  Business logic for published product browsing, cart validation
          (storefront_qty check), checkout (routes to correct PaymentGateway
          Protocol implementation), stock decrement at payment (not cart add),
          order confirmation, and RS256 widget JWT issuance.
          Mode gate: Wholesale Only tenants raise 403.
Depends:  app.core.storefront.models, app.infra.payments, app.api.deps
HITL:     fulfillment_notification
"""
