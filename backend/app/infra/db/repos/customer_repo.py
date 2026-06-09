"""
Feature:  Customer Management
Layer:    Infra / Repository
Module:   app.infra.db.repos.customer_repo
Purpose:  Data access for customers. Implements exact-match lookups (email,
          phone) and name fuzzy match for the 3-tier matching waterfall.
Depends:  app.infra.db.repos.base_repo
HITL:     None — repository only.
"""

from app.infra.db.repos.base_repo import TenantRepository


class CustomerRepository(TenantRepository):
    pass
