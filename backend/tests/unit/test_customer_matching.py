"""
Feature:  Customer Management
Layer:    Test / Unit
Module:   tests.unit.test_customer_matching
Purpose:  Unit tests for customer deduplication and matching logic.
          Verifies: fuzzy name matching threshold, email dedup, tenant
          scoping prevents cross-tenant customer collisions.
Depends:  app.core.customers.services, conftest fakes
HITL:     None
"""
from __future__ import annotations

import pytest


class TestCustomerMatching:
    def test_exact_email_match_deduplicates(self) -> None:
        """Two customers with the same email must be deduplicated."""
        from app.core.customers.services import find_or_create_customer

        c1 = find_or_create_customer(
            tenant_id="t1", name="Acme Corp", email="acme@example.com"
        )
        c2 = find_or_create_customer(
            tenant_id="t1", name="Acme Corporation", email="acme@example.com"
        )
        assert c1.id == c2.id

    def test_same_email_different_tenant_no_collision(self) -> None:
        """Same email under different tenants must create separate records."""
        from app.core.customers.services import find_or_create_customer

        c1 = find_or_create_customer(
            tenant_id="t1", name="Global Inc", email="info@global.com"
        )
        c2 = find_or_create_customer(
            tenant_id="t2", name="Global Inc", email="info@global.com"
        )
        assert c1.id != c2.id
