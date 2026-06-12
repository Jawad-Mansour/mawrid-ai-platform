"""
Feature:  Invoice Management / Customer-Facing Storefront
Layer:    Tests / Unit
Module:   tests.unit.test_invoice_pdf
Purpose:  Unit tests for invoice PDF generation using reportlab.
          Verifies that generate_invoice_pdf produces a valid non-empty PDF
          and that InvoiceData.total is computed correctly.
          No Docker, no external services required.
Depends:  app.infra.documents.invoice_pdf
HITL:     None.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.infra.documents.invoice_pdf import InvoiceData, InvoiceLineItem, generate_invoice_pdf


def _sample_invoice(**overrides: object) -> InvoiceData:
    defaults = dict(
        invoice_id="inv-001",
        invoice_number="INV-001",
        invoice_date=date(2026, 6, 12),
        due_date=date(2026, 7, 12),
        currency="USD",
        status="unpaid",
        tenant_name="Acme Imports LLC",
        tenant_email="billing@acme.com",
        consumer_name="Bob Smith",
        consumer_email="bob@example.com",
        consumer_address="456 Oak Avenue, Beirut, Lebanon",
        items=[
            InvoiceLineItem(product_name="Laptop Stand", qty=2, unit_price=49.99),
            InvoiceLineItem(product_name="USB-C Hub", qty=1, unit_price=29.50),
        ],
    )
    defaults.update(overrides)
    return InvoiceData(**defaults)  # type: ignore[arg-type]


class TestInvoiceLineItem:
    def test_line_total_is_qty_times_price(self) -> None:
        item = InvoiceLineItem(product_name="Widget", qty=3, unit_price=10.0)
        assert item.line_total == 30.0

    def test_line_total_rounds_to_two_decimals(self) -> None:
        item = InvoiceLineItem(product_name="Gadget", qty=3, unit_price=0.1)
        assert item.line_total == pytest.approx(0.3, abs=1e-9)


class TestInvoiceDataTotal:
    def test_total_sums_all_line_totals(self) -> None:
        inv = _sample_invoice()
        # 2 × 49.99 + 1 × 29.50 = 99.98 + 29.50 = 129.48
        assert inv.total == pytest.approx(129.48, abs=0.01)

    def test_total_with_single_item(self) -> None:
        inv = _sample_invoice(items=[InvoiceLineItem("Solo", qty=5, unit_price=20.0)])
        assert inv.total == 100.0

    def test_total_with_empty_items_is_zero(self) -> None:
        inv = _sample_invoice(items=[])
        assert inv.total == 0.0


class TestGenerateInvoicePdf:
    def test_returns_non_empty_bytes(self) -> None:
        inv = _sample_invoice()
        pdf_bytes = generate_invoice_pdf(inv)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000

    def test_output_starts_with_pdf_magic_bytes(self) -> None:
        inv = _sample_invoice()
        pdf_bytes = generate_invoice_pdf(inv)
        assert pdf_bytes[:4] == b"%PDF"

    def test_generates_with_empty_items(self) -> None:
        inv = _sample_invoice(items=[])
        pdf_bytes = generate_invoice_pdf(inv)
        assert pdf_bytes[:4] == b"%PDF"

    def test_generates_with_many_items(self) -> None:
        items = [InvoiceLineItem(f"Product {i}", qty=i, unit_price=float(i)) for i in range(1, 21)]
        inv = _sample_invoice(items=items)
        pdf_bytes = generate_invoice_pdf(inv)
        assert pdf_bytes[:4] == b"%PDF"

    def test_generates_with_unicode_product_names(self) -> None:
        items = [
            InvoiceLineItem("جهاز كمبيوتر", qty=1, unit_price=299.0),
            InvoiceLineItem("Écran LED", qty=2, unit_price=89.0),
        ]
        inv = _sample_invoice(items=items)
        pdf_bytes = generate_invoice_pdf(inv)
        assert pdf_bytes[:4] == b"%PDF"

    def test_generates_with_paid_status(self) -> None:
        inv = _sample_invoice(status="paid")
        pdf_bytes = generate_invoice_pdf(inv)
        assert pdf_bytes[:4] == b"%PDF"
