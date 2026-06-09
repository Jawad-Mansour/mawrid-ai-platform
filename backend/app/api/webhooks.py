"""
Feature:  Payment Webhooks & n8n Callbacks (cross-cutting)
Layer:    API / Router
Module:   app.api.webhooks
Purpose:  Inbound webhook handlers for Stripe, OMT, Whish payment confirmations
          and n8n event callbacks. All webhooks verified via HMAC-SHA256 before
          any processing. Payment confirmation triggers auto-stop (n8n WF-08).
Depends:  app.infra.payments.protocol, app.core.dunning.services, app.api.deps
HITL:     None — webhooks trigger auto-stop, not outbound actions.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
