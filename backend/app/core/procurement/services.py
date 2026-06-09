"""
Feature:  Order Management & Procurement
Layer:    Core / Service
Module:   app.core.procurement.services
Purpose:  Business logic for: order draft CRUD, "Submit Order" (internal save)
          vs "Place Order" (creates purchase_order_send HITL action), shipment
          milestone updates, goods received (atomic stock increment:
          qty_in_stock += qty_received - qty_damaged), discrepancy detection
          (>5% qty → auto-create dispute_letter HITL action), and storefront
          publishing (sets storefront_status='published').
Depends:  app.core.procurement.models, app.core.hitl.services,
          app.infra.db.repos.procurement_repo
HITL:     purchase_order_send, dispute_letter
"""
