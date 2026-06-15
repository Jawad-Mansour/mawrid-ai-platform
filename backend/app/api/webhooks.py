"""
Feature:  Payment Webhooks & n8n Event Callbacks (cross-cutting)
Layer:    API / Router
Module:   app.api.webhooks
Purpose:  Inbound webhook handlers for Stripe payment confirmations
          and n8n event callbacks. Stripe webhooks verified via HMAC-SHA256
          using the Stripe-Signature header. n8n callbacks verified via
          X-N8N-Service-Token header.
          Payment confirmation triggers auto-stop (n8n WF-08) and marks
          invoice paid in one atomic DB write.
Depends:  app.core.dunning.services, app.infra.db.session, app.core.config
HITL:     None — webhooks trigger auto-stop (system action), not outbound actions.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import SessionDep
from app.api.schemas import StrictModel
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Auth helpers ──────────────────────────────────────────────────────────────


def _verify_service_token(token: str | None) -> None:
    settings = get_settings()
    if token is None or not hmac.compare_digest(token, settings.n8n_service_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token.",
        )


def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> None:
    """Validate Stripe-Signature header (v1 scheme)."""
    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = int(parts["t"])
        sig = parts["v1"]
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed Stripe-Signature header.",
        ) from exc

    # Replay protection: reject events older than 5 minutes
    if abs(time.time() - timestamp) > 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe webhook timestamp out of tolerance.",
        )

    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe signature mismatch.",
        )


# ── Request/response schemas ──────────────────────────────────────────────────


class PaymentConfirmedRequest(StrictModel):
    tenant_id: str
    invoice_id: str
    amount_paid: float
    currency: str = "USD"
    payment_reference: str


class EnrichmentDoneRequest(StrictModel):
    tenant_id: str
    document_id: str
    product_count: int
    status: str = "enriched"


class StockThresholdRequest(StrictModel):
    tenant_id: str
    product_id: str
    product_name: str
    qty_in_stock: int
    reorder_threshold: int


class OrderConfirmedRequest(StrictModel):
    tenant_id: str
    order_id: str
    invoice_id: str
    consumer_email: str
    total_amount: float
    currency: str = "USD"


class WebhookResponse(StrictModel):
    status: str
    detail: str


# ── Stripe webhook ────────────────────────────────────────────────────────────


@router.post(
    "/stripe",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Stripe payment confirmation webhook (HMAC-SHA256 verified)",
)
async def stripe_payment_webhook(
    request: Request,
    session: SessionDep,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> WebhookResponse:
    """
    Receives Stripe payment.intent.succeeded events.
    Verifies HMAC-SHA256 signature, marks invoice paid, stops dunning sequences.
    WF-08 triggers this endpoint after Stripe sends the payment webhook to n8n.
    """
    payload = await request.body()

    # Stripe webhook secret comes from Vault in production; use env default in dev
    from app.infra.secrets.vault import get_secrets  # noqa: PLC0415

    try:
        stripe_secret: str = get_secrets().stripe_webhook_secret
    except Exception:
        stripe_secret = "dev-stripe-secret"

    # Signature is mandatory outside dev/test — never accept an unsigned money event
    # in production (an unsigned POST could otherwise mark invoices paid).
    settings = get_settings()
    if stripe_signature:
        _verify_stripe_signature(payload, stripe_signature, stripe_secret)
    elif settings.environment not in ("development", "test"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    import json  # noqa: PLC0415

    try:
        event: dict[str, Any] = json.loads(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    if event.get("type") != "payment_intent.succeeded":
        return WebhookResponse(status="ignored", detail=f"event type {event.get('type')} not handled")

    metadata: dict[str, Any] = event.get("data", {}).get("object", {}).get("metadata", {})
    tenant_id: str = metadata.get("tenant_id", "")
    invoice_id: str = metadata.get("invoice_id", "")

    if not tenant_id or not invoice_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing tenant_id or invoice_id in payment metadata.",
        )

    from app.core.dunning.services import auto_stop_on_payment  # noqa: PLC0415
    from app.infra.db.repos.invoice_repo import InvoiceRepository  # noqa: PLC0415

    invoice_repo = InvoiceRepository(session, tenant_id)
    # Row-lock the invoice so concurrent deliveries of the same event can't both
    # pass the paid_at check and double-fulfil (idempotent under retries/races).
    invoice = await invoice_repo.get_by_id_for_update(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    if invoice.paid_at is None:
        await invoice_repo.mark_paid(invoice_id)
        await auto_stop_on_payment(session, tenant_id, invoice_id)

        # Decrement storefront_qty for each consumer order item atomically
        if invoice.order_id:
            from app.infra.db.repos.consumer_order_repo import (
                ConsumerOrderRepository,  # noqa: PLC0415
            )
            from app.infra.db.repos.product_repo import ProductRepository  # noqa: PLC0415

            order_repo = ConsumerOrderRepository(session, tenant_id)
            product_repo = ProductRepository(session, tenant_id)

            items = await order_repo.list_items(invoice.order_id)
            for item in items:
                ok = await product_repo.decrement_storefront_qty(item.product_id, item.qty)
                if not ok:
                    logger.warning(
                        "storefront_qty_decrement_failed",
                        product_id=item.product_id,
                        order_id=invoice.order_id,
                    )
            await order_repo.set_status(invoice.order_id, "paid")

        await session.commit()
        logger.info("stripe_payment_processed", invoice_id=invoice_id, tenant_id=tenant_id)

        # Fire n8n WF-07 to trigger invoice PDF generation + email
        from app.infra.n8n.client import fire_event  # noqa: PLC0415

        await fire_event(
            "wf07-order-confirmed",
            {
                "tenant_id": tenant_id,
                "invoice_id": invoice_id,
                "order_id": invoice.order_id or "",
                "consumer_email": invoice.contact_email or "",
                "total_amount": float(invoice.amount_due),
            },
        )
    else:
        await session.commit()

    return WebhookResponse(status="ok", detail="payment recorded")


# ── n8n service webhook endpoints ─────────────────────────────────────────────


@router.post(
    "/n8n/enrichment_done",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="n8n notifies backend that enrichment is complete for a document",
)
async def n8n_enrichment_done(
    body: EnrichmentDoneRequest,
    x_n8n_service_token: str | None = Header(default=None, alias="X-N8N-Service-Token"),
) -> WebhookResponse:
    """
    Called by n8n WF-03 after enrichment jobs complete.
    Backend logs the event; the actual catalog update is done by the ARQ worker.
    """
    _verify_service_token(x_n8n_service_token)
    logger.info(
        "n8n_enrichment_done",
        document_id=body.document_id,
        product_count=body.product_count,
        tenant_id=body.tenant_id,
    )
    return WebhookResponse(
        status="ok",
        detail=f"enrichment_done logged for document {body.document_id}",
    )


@router.post(
    "/n8n/stock_threshold",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="n8n notifies backend that a product has hit its reorder threshold",
)
async def n8n_stock_threshold(
    body: StockThresholdRequest,
    session: SessionDep,
    x_n8n_service_token: str | None = Header(default=None, alias="X-N8N-Service-Token"),
) -> WebhookResponse:
    """
    Called by n8n WF-11 when stock drops to or below reorder_threshold.
    Backend triggers the reorder signal: finds best supplier, creates HITL PO draft.
    The actual reorder logic is in the Stock Monitor specialist / procurement service.
    """
    _verify_service_token(x_n8n_service_token)
    logger.info(
        "n8n_stock_threshold_received",
        product_id=body.product_id,
        qty=body.qty_in_stock,
        threshold=body.reorder_threshold,
        tenant_id=body.tenant_id,
    )
    from app.core.suppliers.services import trigger_reorder_check  # noqa: PLC0415

    try:
        await trigger_reorder_check(session, body.tenant_id)
        await session.commit()
    except Exception as exc:
        logger.warning("reorder_signal_failed", error=str(exc))

    return WebhookResponse(
        status="accepted",
        detail=f"reorder signal queued for product {body.product_id}",
    )


@router.post(
    "/n8n/order_confirmed",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="n8n notifies backend of confirmed consumer order (WF-07)",
)
async def n8n_order_confirmed(
    body: OrderConfirmedRequest,
    x_n8n_service_token: str | None = Header(default=None, alias="X-N8N-Service-Token"),
) -> WebhookResponse:
    """
    Called by n8n WF-07 after consumer order is confirmed by payment gateway.
    Backend logs the confirmation; invoice PDF is served via /invoices/{id}/pdf-url.
    """
    _verify_service_token(x_n8n_service_token)
    logger.info(
        "n8n_order_confirmed",
        order_id=body.order_id,
        invoice_id=body.invoice_id,
        tenant_id=body.tenant_id,
    )
    return WebhookResponse(
        status="accepted",
        detail=f"order {body.order_id} confirmation logged",
    )
