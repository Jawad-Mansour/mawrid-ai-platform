"""
Feature:  Customer-Facing Storefront
Layer:    API / Router
Module:   app.api.storefront
Purpose:  HTTP routes for published product browsing, cart, checkout (Stripe /
          OMT / Whish), order confirmation, and consumer order status.
          Mode-gated: Wholesale Only tenants receive 403 on all /store/ routes.
          Triggers n8n WF-07 (invoice) on order confirmation.
Depends:  app.core.storefront.services, app.infra.payments, app.api.deps
HITL:     fulfillment_notification
"""

from fastapi import APIRouter

router = APIRouter(prefix="/store", tags=["storefront"])
