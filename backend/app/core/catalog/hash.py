"""
Feature:  Catalog Enrichment Pipeline
Layer:    Core / Utility
Module:   app.core.catalog.hash
Purpose:  Canonical product hash function. SHA-256 of the colon-delimited
          string "tenant_id:product_name:sku_if_present". Price is intentionally
          excluded so price changes do not cause re-enrichment.
Depends:  hashlib (stdlib)
HITL:     None.
"""

import hashlib


def compute_product_hash(tenant_id: str, product_name: str, sku: str | None = None) -> str:
    raw = f"{tenant_id}:{product_name}:{sku or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()
