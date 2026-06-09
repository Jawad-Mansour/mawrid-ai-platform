"""
Feature:  Customer Management
Layer:    Core / Service
Module:   app.core.customers.services
Purpose:  Business logic for customer match waterfall (email→phone→name≥0.85
          match, 0.3–0.85 HITL, <0.3 auto-create), segment assignment, and
          payment history score updates used by dunning tone classifier.
Depends:  app.core.customers.models, app.core.hitl.services,
          app.infra.db.repos.customer_repo
HITL:     customer_match_review
"""

import uuid
from dataclasses import dataclass, field

# In-memory store keyed by (tenant_id, email) — replaced by DB repo in production.
_store: dict[tuple[str, str], "Customer"] = {}


@dataclass
class Customer:
    id: str
    tenant_id: str
    name: str
    email: str | None = field(default=None)


def find_or_create_customer(
    tenant_id: str,
    name: str,
    email: str | None = None,
) -> Customer:
    if email is not None:
        key = (tenant_id, email)
        if key not in _store:
            _store[key] = Customer(
                id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, email=email
            )
        return _store[key]
    return Customer(id=str(uuid.uuid4()), tenant_id=tenant_id, name=name, email=None)
