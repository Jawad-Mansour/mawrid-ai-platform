"""
Feature:  Storefront Publishing
Layer:    Test / Unit
Module:   tests.unit.test_publishing
Purpose:  Unit tests for the product publishing gate. Verifies the full
          lifecycle preconditions: goods_received → retail_price_set → published.
          A product missing any prerequisite must be blocked from publishing.
Depends:  app.core.catalog.services, conftest fakes
HITL:     product_published
"""
from __future__ import annotations

import pytest


class TestPublishingGate:
    def test_cannot_publish_without_goods_received(self) -> None:
        """A product that hasn't been physically received must not be publishable."""
        from app.core.catalog.services import can_publish

        result = can_publish(
            enrichment_status="enriched",
            lifecycle_status="ordered",  # not yet in_stock
            retail_price=None,
        )
        assert result is False

    def test_cannot_publish_without_retail_price(self) -> None:
        """A product with no retail price must not be publishable."""
        from app.core.catalog.services import can_publish

        result = can_publish(
            enrichment_status="enriched",
            lifecycle_status="in_stock",
            retail_price=None,
        )
        assert result is False

    def test_can_publish_when_all_conditions_met(self) -> None:
        """Publishing must succeed when all 3 preconditions are met."""
        from app.core.catalog.services import can_publish

        result = can_publish(
            enrichment_status="enriched",
            lifecycle_status="in_stock",
            retail_price=29.99,
        )
        assert result is True

    def test_published_product_visible_on_storefront(self) -> None:
        """Only published products must have storefront_status = 'published'."""
        from app.core.catalog.services import publish_product

        result = publish_product(
            tenant_id="t1",
            product_id="p1",
            retail_price=49.99,
        )
        assert result.storefront_status == "published"
