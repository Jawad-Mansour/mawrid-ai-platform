"""
Feature:  Invoice Management
Layer:    API / Router
Module:   app.api.invoices
Purpose:  HTTP routes for invoice CRUD, payment webhook, aging report,
          and PDF download (presigned MinIO URL).
          Payment webhook (POST /invoices/{id}/paid) atomically marks paid +
          stops dunning sequences + rejects pending HITL actions.
          Aging endpoint (GET /invoices/aging) returns bucket totals for
          the operations dashboard.
Depends:  app.core.dunning.services, app.infra.db.repos.invoice_repo,
          app.infra.storage.minio, app.api.deps
HITL:     None — invoice reads/creation/payment are not external writes.
          (Payment webhook calls auto_stop_on_payment which cancels HITL actions)
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.models.dunning import Invoice
from app.infra.db.repos.invoice_repo import InvoiceRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class InvoiceCreate(StrictModel):
    invoice_id: str
    direction: str  # payable | receivable
    invoice_type: str  # b2b | b2c
    amount_due: float
    invoice_date: str  # ISO date YYYY-MM-DD
    due_date: str  # ISO date YYYY-MM-DD
    payment_terms_days: int = 30
    currency: str = "USD"
    contact_email: str | None = None
    contact_name: str | None = None
    contact_language: str | None = None
    customer_id: str | None = None
    supplier_id: str | None = None
    order_id: str | None = None
    pdf_key: str | None = None


class InvoiceResponse(StrictModel):
    invoice_id: str
    direction: str
    invoice_type: str
    amount_due: float
    invoice_date: str
    due_date: str
    status: str
    paid_at: str | None
    currency: str
    contact_email: str | None
    contact_name: str | None
    customer_id: str | None
    supplier_id: str | None
    created_at: str


class AgingResponse(StrictModel):
    as_of_date: str
    buckets: dict[str, float]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _invoice_to_response(inv: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        invoice_id=inv.invoice_id,
        direction=inv.direction,
        invoice_type=inv.invoice_type,
        amount_due=float(inv.amount_due),
        invoice_date=inv.invoice_date.isoformat(),
        due_date=inv.due_date.isoformat(),
        status=inv.status,
        paid_at=inv.paid_at.isoformat() if inv.paid_at else None,
        currency=inv.currency,
        contact_email=inv.contact_email,
        contact_name=inv.contact_name,
        customer_id=inv.customer_id,
        supplier_id=inv.supplier_id,
        created_at=inv.created_at.isoformat(),
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice",
)
async def create_invoice(
    body: InvoiceCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> InvoiceResponse:
    """Create an invoice record. Called by procurement workflow and n8n WF-07."""
    repo = InvoiceRepository(session, current_user.tenant_id)

    # Idempotency: return existing record if already created
    existing = await repo.get_by_id(body.invoice_id)
    if existing is not None:
        return _invoice_to_response(existing)

    invoice = Invoice(
        invoice_id=body.invoice_id,
        tenant_id=current_user.tenant_id,
        direction=body.direction,
        invoice_type=body.invoice_type,
        amount_due=body.amount_due,
        invoice_date=date.fromisoformat(body.invoice_date),
        due_date=date.fromisoformat(body.due_date),
        payment_terms_days=body.payment_terms_days,
        currency=body.currency,
        status="unpaid",
        contact_email=body.contact_email,
        contact_name=body.contact_name,
        contact_language=body.contact_language,
        customer_id=body.customer_id,
        supplier_id=body.supplier_id,
        order_id=body.order_id,
        pdf_key=body.pdf_key,
    )
    created = await repo.create(invoice)
    await session.commit()
    logger.info(
        "invoice_created",
        invoice_id=body.invoice_id,
        direction=body.direction,
        tenant_id=current_user.tenant_id,
    )
    return _invoice_to_response(created)


@router.get(
    "",
    response_model=list[InvoiceResponse],
    summary="List invoices with optional filters",
)
async def list_invoices(
    current_user: CurrentUser,
    session: SessionDep,
    direction: str | None = None,
    invoice_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[InvoiceResponse]:
    repo = InvoiceRepository(session, current_user.tenant_id)
    invoices = await repo.list_all(
        limit=limit,
        direction=direction,
        invoice_type=invoice_type,
        status=status,
    )
    return [_invoice_to_response(inv) for inv in invoices]


@router.get(
    "/aging",
    response_model=AgingResponse,
    summary="Receivables aging report — bucket totals by overdue days",
)
async def get_aging_report(
    current_user: CurrentUser,
    session: SessionDep,
) -> AgingResponse:
    """
    Returns aging buckets for unpaid receivable invoices:
    current (not yet due), 1-30, 31-60, 61-90, over_90.
    Amounts in the tenant's primary currency (mixed-currency totals not converted).
    """
    repo = InvoiceRepository(session, current_user.tenant_id)
    today = date.today()
    buckets: dict[str, Any] = await repo.get_aging_buckets(today)
    return AgingResponse(as_of_date=today.isoformat(), buckets=buckets)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get a single invoice by ID",
)
async def get_invoice(
    invoice_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> InvoiceResponse:
    repo = InvoiceRepository(session, current_user.tenant_id)
    invoice = await repo.get_by_id(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return _invoice_to_response(invoice)


@router.post(
    "/{invoice_id}/paid",
    summary="Mark invoice as paid (payment webhook). Atomically stops all dunning.",
)
async def mark_invoice_paid(
    invoice_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """
    Payment reconciliation endpoint. Atomically:
    1. Marks invoice.paid_at = now, status = 'paid'
    2. Stops all active dunning sequences for this invoice
    3. Rejects all pending HITL dunning actions for this invoice
    Idempotent: returns current state if invoice already marked paid.
    """
    from app.core.dunning.services import auto_stop_on_payment  # noqa: PLC0415

    result = await auto_stop_on_payment(
        session=session,
        tenant_id=current_user.tenant_id,
        invoice_id=invoice_id,
    )
    await session.commit()

    logger.info(
        "invoice_marked_paid",
        invoice_id=invoice_id,
        tenant_id=current_user.tenant_id,
        **result,
    )
    response: dict[str, Any] = {"invoice_id": invoice_id, "status": "paid", **result}
    return response


@router.post(
    "/generate",
    summary="Generate invoice PDF → upload to MinIO → update invoice.pdf_key (called by n8n WF-07)",
)
async def generate_invoice_pdf(
    body: InvoiceCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """
    Generate a PDF for the given invoice_id, upload to MinIO, update invoice.pdf_key,
    return a presigned URL. Called by n8n WF-07 after payment confirmation.
    Idempotent: if pdf_key already set, returns existing presigned URL.
    """
    from sqlalchemy import update  # noqa: PLC0415

    from app.infra.db.models.dunning import Invoice as InvoiceModel  # noqa: PLC0415
    from app.infra.db.repos.consumer_order_repo import ConsumerOrderRepository  # noqa: PLC0415
    from app.infra.db.repos.tenant_repo import TenantRepo  # noqa: PLC0415
    from app.infra.documents.invoice_pdf import (  # noqa: PLC0415
        InvoiceData,
        InvoiceLineItem,
        generate_invoice_pdf,
    )
    from app.infra.storage.minio import get_presigned_url, upload_document  # noqa: PLC0415

    repo = InvoiceRepository(session, current_user.tenant_id)
    invoice = await repo.get_by_id(body.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    # Idempotent: return existing URL if already generated
    if invoice.pdf_key:
        url = await get_presigned_url(current_user.tenant_id, invoice.pdf_key, expires_seconds=900)
        return {"invoice_id": invoice.invoice_id, "pdf_key": invoice.pdf_key, "pdf_url": url}

    # Load line items from consumer order if linked
    line_items: list[InvoiceLineItem] = []
    if invoice.order_id:
        order_repo = ConsumerOrderRepository(session, current_user.tenant_id)
        order_items = await order_repo.list_items(invoice.order_id)
        line_items = [
            InvoiceLineItem(
                product_name=item.product_id,  # product_name resolved at render if needed
                qty=item.qty,
                unit_price=float(item.unit_price),
            )
            for item in order_items
        ]

    # Tenant name from repo (fallback to tenant_id)
    tenant_repo = TenantRepo(session)
    tenant = await tenant_repo.get_by_id(current_user.tenant_id)
    tenant_name = tenant.name if tenant else current_user.tenant_id

    inv_data = InvoiceData(
        invoice_id=invoice.invoice_id,
        invoice_number=invoice.invoice_id[:8].upper(),
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        status=invoice.status,
        tenant_name=tenant_name,
        tenant_email=invoice.contact_email or "",
        consumer_name=invoice.contact_name or "Valued Customer",
        consumer_email=invoice.contact_email or "",
        consumer_address="",
        items=line_items
        if line_items
        else [InvoiceLineItem("Order items", 1, float(invoice.amount_due))],
    )

    pdf_bytes = generate_invoice_pdf(inv_data)
    object_name = f"invoices/{invoice.invoice_id}.pdf"
    pdf_key = await upload_document(
        tenant_id=current_user.tenant_id,
        object_name=object_name,
        data=pdf_bytes,
        content_type="application/pdf",
    )

    # Update invoice.pdf_key in DB
    await session.execute(
        update(InvoiceModel)
        .where(InvoiceModel.invoice_id == invoice.invoice_id)
        .values(pdf_key=pdf_key)
    )
    await session.commit()

    url = await get_presigned_url(current_user.tenant_id, object_name, expires_seconds=900)
    logger.info(
        "invoice_pdf_generated",
        invoice_id=invoice.invoice_id,
        pdf_key=pdf_key,
        tenant_id=current_user.tenant_id,
    )
    return {"invoice_id": invoice.invoice_id, "pdf_key": pdf_key, "pdf_url": url}


@router.get(
    "/{invoice_id}/pdf-url",
    summary="Get a presigned MinIO URL for the invoice PDF (valid 15 min)",
)
async def get_invoice_pdf_url(
    invoice_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    from app.infra.storage.minio import get_presigned_url  # noqa: PLC0415

    repo = InvoiceRepository(session, current_user.tenant_id)
    invoice = await repo.get_by_id(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if not invoice.pdf_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No PDF attached to this invoice.",
        )

    url = await get_presigned_url(current_user.tenant_id, invoice.pdf_key, expires_seconds=900)
    return {"invoice_id": invoice_id, "pdf_url": url, "expires_in_seconds": "900"}
