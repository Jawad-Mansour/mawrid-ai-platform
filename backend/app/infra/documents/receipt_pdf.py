"""
Feature:  Inventory — Goods-Received Report
Layer:    Infra / Documents
Module:   app.infra.documents.receipt_pdf
Purpose:  Generate a professional goods-received / container-arrival report PDF
          (reportlab Platypus): per-product checklist of ordered vs received vs
          damaged, notes, and an overall outcome. Sent to the supplier — a clean
          receipt when all is good, or evidence attached to a dispute when not.
Depends:  reportlab
HITL:     None — document generation only.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class ReceiptLine:
    product_name: str
    sku: str
    ordered: int
    received: int
    damaged: int
    note: str = ""


@dataclass
class ReceiptData:
    po_number: str
    supplier_name: str
    tenant_name: str
    received_on: date
    carrier: str = ""
    container: str = ""
    lines: list[ReceiptLine] = field(default_factory=list)
    notes: str = ""

    @property
    def all_good(self) -> bool:
        return all(li.received >= li.ordered and li.damaged == 0 for li in self.lines)


def generate_receipt_pdf(data: ReceiptData) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#7C4DFF")
    ok = colors.HexColor("#059669")
    bad = colors.HexColor("#DC2626")

    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=brand, fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#374151"), fontSize=11, spaceAfter=2)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=14)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.gray)
    story: list[Any] = []

    story.append(Paragraph("Goods Received Report", h1))
    story.append(Paragraph(f"{data.tenant_name} — confirming receipt for {data.po_number}", small))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=brand))
    story.append(Spacer(1, 0.4 * cm))

    meta = [
        ["Purchase Order", data.po_number],
        ["Supplier", data.supplier_name],
        ["Received on", data.received_on.strftime("%d %b %Y")],
    ]
    if data.carrier:
        meta.append(["Carrier", data.carrier])
    if data.container:
        meta.append(["Container", data.container])
    mt = Table(meta, colWidths=[3.5 * cm, 9 * cm])
    mt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Checklist", h2))
    headers = ["Code", "Product", "Ordered", "Received", "Damaged", "Note"]
    rows: list[list[str]] = [headers]
    for li in data.lines:
        rows.append([li.sku or "—", li.product_name, str(li.ordered), str(li.received), str(li.damaged), li.note or "—"])
    tbl = Table(rows, colWidths=[2.2 * cm, 5.3 * cm, 1.8 * cm, 1.9 * cm, 1.9 * cm, 3.4 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (4, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, li in enumerate(data.lines, start=1):
        if li.received < li.ordered or li.damaged > 0:
            style.append(("TEXTCOLOR", (2, i), (4, i), bad))
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    outcome = "All items received in full and in good condition. Thank you." if data.all_good \
        else "Discrepancies / damage were found (highlighted above). Please review — a formal claim may follow."
    story.append(Paragraph("Outcome", h2))
    story.append(Paragraph(outcome, ParagraphStyle("O", parent=body, textColor=ok if data.all_good else bad)))
    if data.notes:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"Notes: {data.notes}", body))

    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(f"{data.tenant_name} · generated by Mawrid", small))
    doc.build(story)
    return buf.getvalue()
