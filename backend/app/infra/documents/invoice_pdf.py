"""
Feature:  Customer-Facing Storefront / Invoice Management
Layer:    Infra / Documents
Module:   app.infra.documents.invoice_pdf
Purpose:  Generate a B2C invoice PDF using reportlab Platypus. Produces a
          professional invoice with tenant branding, consumer details, line items,
          and totals. Returns PDF bytes — caller handles MinIO upload.
          Called by POST /invoices/generate after payment confirmation.
Depends:  reportlab
HITL:     None — document generation only.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class InvoiceLineItem:
    product_name: str
    qty: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass
class InvoiceData:
    invoice_id: str
    invoice_number: str
    invoice_date: date
    due_date: date
    currency: str
    status: str

    # Tenant (seller)
    tenant_name: str
    tenant_email: str

    # Consumer (buyer)
    consumer_name: str
    consumer_email: str
    consumer_address: str

    # Line items
    items: list[InvoiceLineItem]

    @property
    def total(self) -> float:
        return round(sum(i.line_total for i in self.items), 2)


def generate_invoice_pdf(data: InvoiceData) -> bytes:
    """
    Render an InvoiceData to a PDF and return the raw bytes.
    Layout: header → invoice meta → consumer details → items table → total → footer.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    _brand = colors.HexColor("#1A56DB")  # Mawrid blue

    h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], textColor=_brand, fontSize=22, spaceAfter=4
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#374151"),
        fontSize=11,
        spaceAfter=2,
    )
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=14)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.gray)

    story: list[Any] = []

    # ── Header ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(data.tenant_name, h1))
    story.append(Paragraph(data.tenant_email, small))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_brand))
    story.append(Spacer(1, 0.4 * cm))

    # ── Invoice meta ────────────────────────────────────────────────────────────
    meta_data = [
        ["Invoice #", data.invoice_number],
        ["Invoice Date", data.invoice_date.strftime("%d %b %Y")],
        ["Due Date", data.due_date.strftime("%d %b %Y")],
        ["Status", data.status.upper()],
        ["Currency", data.currency],
    ]
    meta_table = Table(meta_data, colWidths=[3.5 * cm, 6 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.6 * cm))

    # ── Bill To ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("Bill To", h2))
    story.append(Paragraph(data.consumer_name, body))
    story.append(Paragraph(data.consumer_email, body))
    if data.consumer_address:
        story.append(Paragraph(data.consumer_address, body))
    story.append(Spacer(1, 0.5 * cm))

    # ── Line items table ────────────────────────────────────────────────────────
    col_widths = [8 * cm, 2 * cm, 3.5 * cm, 3.5 * cm]
    headers = ["Product", "Qty", f"Unit Price ({data.currency})", f"Total ({data.currency})"]
    rows: list[list[str]] = [headers]
    for item in data.items:
        rows.append(
            [
                item.product_name,
                str(item.qty),
                f"{item.unit_price:,.2f}",
                f"{item.line_total:,.2f}",
            ]
        )

    items_table = Table(rows, colWidths=col_widths)
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _brand),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Total ────────────────────────────────────────────────────────────────────
    total_data = [["", "", "TOTAL", f"{data.total:,.2f} {data.currency}"]]
    total_table = Table(total_data, colWidths=col_widths)
    total_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("TEXTCOLOR", (2, 0), (-1, -1), _brand),
                ("LINEABOVE", (2, 0), (-1, 0), 1, _brand),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(total_table)
    story.append(Spacer(1, 1 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("Thank you for your order. — Mawrid Platform", small))

    doc.build(story)
    return buf.getvalue()
