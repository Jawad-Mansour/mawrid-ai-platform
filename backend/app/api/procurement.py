"""
Feature:  Order Management & Procurement
Layer:    API / Router
Module:   app.api.procurement
Purpose:  HTTP routes for order draft CRUD, "Place Order" trigger (creates
          purchase_order_send HITL action), shipment tracking, goods receiving,
          and storefront publishing. Triggers n8n WF-04, WF-05, WF-06.
Depends:  app.core.procurement.services, app.core.hitl.services, app.api.deps
HITL:     purchase_order_send, dispute_letter
"""
from fastapi import APIRouter

router = APIRouter(prefix="/procurement", tags=["procurement"])
