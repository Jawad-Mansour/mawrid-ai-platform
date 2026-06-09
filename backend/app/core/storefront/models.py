"""
Feature:  Customer-Facing Storefront
Layer:    Core / Domain Models
Module:   app.core.storefront.models
Purpose:  Pydantic v2 domain models for Cart, Order (consumer), PaymentIntent,
          and StockReservation. Key invariant: storefront_qty is independent of
          qty_in_stock. Stock decrement happens at payment confirmation, not cart
          add. Widget JWT uses RS256.
Depends:  pydantic
HITL:     fulfillment_notification
"""
from pydantic import BaseModel


class CartItem(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: str
    quantity: int
    unit_price: float


class StorefrontOrder(BaseModel):
    model_config = {"extra": "forbid"}

    order_id: str
    tenant_id: str
    customer_id: str
    items: list[CartItem]
    payment_gateway: str  # stripe | omt | whish
    total_amount: float
    status: str = "pending_payment"
