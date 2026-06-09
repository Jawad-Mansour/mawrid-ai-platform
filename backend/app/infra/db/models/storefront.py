"""
Feature:  Customer-Facing Store
Layer:    Infra / DB Models
Module:   app.infra.db.models.storefront
Purpose:  SQLAlchemy ORM models for `consumer_orders` and `consumer_order_items`.
          Consumer orders are created at checkout. Consumer purchases decrement
          storefront_qty (not qty_in_stock directly). Fulfillment status is
          tracked independently of inventory status. Payment is via Stripe/OMT/Whish.
Depends:  app.infra.db.base, sqlalchemy
HITL:     fulfillment_notification (on order fulfillment update)
"""
