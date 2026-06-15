"""
Feature:  Customer-Facing Storefront
Layer:    Core / Service
Module:   app.core.storefront.services
Purpose:  Pure storefront business rules — cart-line evaluation (published +
          stock checks) and order total calculation. No infra/HTTP coupling:
          the API router (app.api.storefront) supplies product data from repos
          and maps these results to HTTP responses. Keeping these rules here
          makes them unit-testable in isolation and reusable by the agent layer.
Depends:  (stdlib only)
HITL:     fulfillment_notification is created by admin after payment, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Cart line outcome statuses
STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"
STATUS_INSUFFICIENT = "insufficient_qty"


@dataclass
class CartLineResult:
    """Outcome of evaluating one cart line. `item` is the API-facing dict and
    `error` is a human-readable message (None when the line is OK)."""

    product_id: str
    status: str
    item: dict[str, Any]
    error: str | None


def evaluate_cart_line(
    product_id: str,
    *,
    exists_and_published: bool,
    product_name: str,
    available_qty: int,
    requested_qty: int,
    unit_price: float,
) -> CartLineResult:
    """
    Evaluate a single cart line against published status and available stock.
    Pure function — caller supplies product facts loaded from the repo.
    """
    if not exists_and_published:
        return CartLineResult(
            product_id=product_id,
            status=STATUS_UNAVAILABLE,
            item={"product_id": product_id, "status": STATUS_UNAVAILABLE},
            error=f"Product {product_id} is not available.",
        )
    if available_qty < requested_qty:
        return CartLineResult(
            product_id=product_id,
            status=STATUS_INSUFFICIENT,
            item={
                "product_id": product_id,
                "status": STATUS_INSUFFICIENT,
                "available": available_qty,
                "requested": requested_qty,
            },
            error=(
                f"Only {available_qty} unit(s) of '{product_name}' available; "
                f"requested {requested_qty}."
            ),
        )
    return CartLineResult(
        product_id=product_id,
        status=STATUS_OK,
        item={
            "product_id": product_id,
            "product_name": product_name,
            "status": STATUS_OK,
            "unit_price": unit_price,
            "qty": requested_qty,
        },
        error=None,
    )


def calculate_order_total(lines: list[tuple[float, int]]) -> float:
    """Sum (unit_price × qty) over all lines, rounded to 2 decimals."""
    return round(sum(price * qty for price, qty in lines), 2)
