"""
Feature:  Customer-Facing Storefront
Layer:    Tests / Unit
Module:   tests.unit.test_storefront_core
Purpose:  Unit tests for the pure storefront business rules in
          app.core.storefront.services (cart-line evaluation + order total).
Depends:  app.core.storefront.services
HITL:     None.
"""

from __future__ import annotations

from app.core.storefront.services import (
    STATUS_INSUFFICIENT,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    calculate_order_total,
    evaluate_cart_line,
)


class TestEvaluateCartLine:
    def test_unavailable_when_not_published(self) -> None:
        r = evaluate_cart_line(
            "p1",
            exists_and_published=False,
            product_name="",
            available_qty=0,
            requested_qty=1,
            unit_price=0.0,
        )
        assert r.status == STATUS_UNAVAILABLE
        assert r.error is not None
        assert r.item == {"product_id": "p1", "status": STATUS_UNAVAILABLE}

    def test_insufficient_qty(self) -> None:
        r = evaluate_cart_line(
            "p1",
            exists_and_published=True,
            product_name="Widget",
            available_qty=2,
            requested_qty=5,
            unit_price=10.0,
        )
        assert r.status == STATUS_INSUFFICIENT
        assert r.item["available"] == 2  # noqa: PLR2004
        assert r.item["requested"] == 5  # noqa: PLR2004
        assert "Widget" in (r.error or "")

    def test_ok_line(self) -> None:
        r = evaluate_cart_line(
            "p1",
            exists_and_published=True,
            product_name="Widget",
            available_qty=10,
            requested_qty=3,
            unit_price=15.0,
        )
        assert r.status == STATUS_OK
        assert r.error is None
        assert r.item["unit_price"] == 15.0  # noqa: PLR2004
        assert r.item["qty"] == 3  # noqa: PLR2004


class TestCalculateOrderTotal:
    def test_empty_is_zero(self) -> None:
        assert calculate_order_total([]) == 0.0

    def test_sums_and_rounds(self) -> None:
        assert calculate_order_total([(15.0, 2), (9.99, 1)]) == 39.99  # noqa: PLR2004

    def test_rounds_to_two_decimals(self) -> None:
        assert calculate_order_total([(0.1, 3)]) == 0.3  # noqa: PLR2004
