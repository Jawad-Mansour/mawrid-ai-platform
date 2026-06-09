"""
Feature:  Customer Management
Layer:    API / Router
Module:   app.api.customers
Purpose:  HTTP routes for customer CRUD, segment assignment, match review
          queue, and payment history score retrieval.
Depends:  app.core.customers.services, app.api.deps
HITL:     customer_match_review
"""

from fastapi import APIRouter

router = APIRouter(prefix="/customers", tags=["customers"])
