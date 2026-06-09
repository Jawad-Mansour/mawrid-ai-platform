"""
Feature:  Supplier Intelligence
Layer:    API / Router
Module:   app.api.suppliers
Purpose:  HTTP routes for supplier CRUD, delivery event recording, score
          retrieval, discovery request submission, and reorder threshold config.
Depends:  app.core.suppliers.services, app.api.deps
HITL:     supplier_outreach, supplier_match_review, purchase_order_send (reorder)
"""

from fastapi import APIRouter

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
