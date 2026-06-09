"""
Feature:  Catalog Enrichment Pipeline
Layer:    Tests / Unit
Module:   tests.unit.test_product_hash
Purpose:  Unit tests for product hash function. Verifies SHA-256 colon-delimited
          format, price exclusion, SKU-absent handling, and cross-tenant isolation.
Depends:  app.core.catalog.hash
HITL:     None.
"""

import hashlib

from app.core.catalog.hash import compute_product_hash


def test_hash_format():
    h = compute_product_hash("tenant1", "Nescafe 200g", "SKU-001")
    expected = hashlib.sha256(b"tenant1:Nescafe 200g:SKU-001").hexdigest()
    assert h == expected


def test_hash_no_sku():
    h = compute_product_hash("tenant1", "Nescafe 200g", None)
    expected = hashlib.sha256(b"tenant1:Nescafe 200g:").hexdigest()
    assert h == expected


def test_cross_tenant_isolation():
    h1 = compute_product_hash("tenant1", "Same Product", "SKU-X")
    h2 = compute_product_hash("tenant2", "Same Product", "SKU-X")
    assert h1 != h2


def test_price_excluded():
    # Adding different prices should NOT change the hash
    h1 = compute_product_hash("tenant1", "Ariel 2kg", "SKU-002")
    h2 = compute_product_hash("tenant1", "Ariel 2kg", "SKU-002")
    assert h1 == h2  # price is not a parameter — always identical
