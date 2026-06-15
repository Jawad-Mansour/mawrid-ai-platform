"""
Feature:  Customer-Facing Storefront
Layer:    API / Router
Module:   app.api.storefront
Purpose:  Guest-accessible HTTP routes for the consumer store: published product
          listing, product detail (with presigned image URL), cart validation,
          checkout (creates order + invoice + payment intent), and order status.
          Mode-gated: Wholesale Only tenants receive 403 on all /store/ routes.
          Checkout fires n8n WF-07 on payment initiation; qty decremented
          atomically at payment confirmation (Stripe webhook handler).
          Tenant identity supplied via X-Tenant-ID header (no consumer login
          in capstone; Wave 3 adds consumer accounts).
Depends:  app.infra.db.repos.*, app.infra.payments.*, app.infra.n8n.client,
          app.infra.secrets.vault, app.infra.db.session
HITL:     None — consumer checkout is automated; fulfillment_notification HITL
          is created separately by admin after order is paid.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.api.schemas import StrictModel
from app.core.storefront.services import calculate_order_total, evaluate_cart_line
from app.infra.db.repos.consumer_order_repo import ConsumerOrderRepository
from app.infra.db.repos.invoice_repo import InvoiceRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.db.repos.tenant_repo import TenantRepo
from app.infra.storage.minio import get_presigned_url

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/store", tags=["storefront"])

_WHOLESALE_ONLY = "wholesale_only"


# ── Tenant resolution ──────────────────────────────────────────────────────────


async def _get_storefront_tenant(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Tenant-ID header is required for storefront access.",
        )
    return x_tenant_id


StorefrontTenantId = Annotated[str, Depends(_get_storefront_tenant)]


async def _check_mode_gate(tenant_id: str, session: AsyncSession) -> None:
    """Raise 403 if the tenant is wholesale_only (storefront is disabled)."""
    tenant_repo = TenantRepo(session)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if tenant is not None and tenant.mode == _WHOLESALE_ONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Storefront is not enabled for this account (Wholesale Only mode).",
        )


# ── Payment gateway factory ────────────────────────────────────────────────────


def _get_gateway(payment_method: str) -> Any:
    """Return the correct payment gateway instance using Vault credentials."""
    from app.infra.secrets.vault import get_secrets  # noqa: PLC0415

    secrets = get_secrets()
    if payment_method == "stripe":
        from app.infra.payments.stripe import StripeGateway  # noqa: PLC0415

        return StripeGateway(api_key=secrets.stripe_secret_key)
    if payment_method == "omt":
        from app.infra.payments.omt import OMTGateway  # noqa: PLC0415

        return OMTGateway(
            api_key=getattr(secrets, "omt_api_key", ""),
            webhook_secret=getattr(secrets, "omt_webhook_secret", ""),
        )
    if payment_method == "whish":
        from app.infra.payments.whish import WhishGateway  # noqa: PLC0415

        return WhishGateway(
            api_key=getattr(secrets, "whish_api_key", ""),
            webhook_secret=getattr(secrets, "whish_webhook_secret", ""),
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unsupported payment method: {payment_method}",
    )


# ── Response schemas ───────────────────────────────────────────────────────────


class StorefrontProductResponse(StrictModel):
    product_id: str
    product_name: str
    description: str | None
    retail_price: float | None
    storefront_qty: int
    currency: str | None
    image_url: str | None  # presigned MinIO URL; None if no image


class StorefrontProductDetail(StorefrontProductResponse):
    specifications: dict[str, Any] | None
    enrichment_source: str | None


class CartItem(StrictModel):
    product_id: str
    qty: int


class CartValidationRequest(StrictModel):
    items: list[CartItem]


class CartValidationResponse(StrictModel):
    valid: bool
    items: list[dict[str, Any]]
    errors: list[str]


class CheckoutRequest(StrictModel):
    items: list[CartItem]
    consumer_name: str
    consumer_email: str
    consumer_phone: str | None = None
    delivery_address: str
    payment_method: str  # stripe | omt | whish
    currency: str = "USD"
    language: str = "en"


class CheckoutResponse(StrictModel):
    order_id: str
    invoice_id: str
    total_amount: float
    currency: str
    payment_method: str
    payment_details: dict[str, Any]


class OrderStatusResponse(StrictModel):
    order_id: str
    status: str
    total_amount: float
    payment_gateway: str
    created_at: str


# ── GET /store/products ────────────────────────────────────────────────────────


@router.get(
    "/products",
    response_model=list[StorefrontProductResponse],
    summary="List all published products for a tenant's storefront",
)
async def list_published_products(
    tenant_id: StorefrontTenantId,
    session: SessionDep,
) -> list[StorefrontProductResponse]:
    await _check_mode_gate(tenant_id, session)
    repo = ProductRepository(session, tenant_id)
    products = await repo.list_published(limit=500)
    result: list[StorefrontProductResponse] = []
    for p in products:
        image_url: str | None = None
        if p.image_path:
            with contextlib.suppress(Exception):
                image_url = await get_presigned_url(tenant_id, p.image_path, expires_seconds=3600)
        result.append(
            StorefrontProductResponse(
                product_id=p.product_id,
                product_name=p.product_name,
                description=p.description,
                retail_price=float(p.retail_price) if p.retail_price is not None else None,
                storefront_qty=p.storefront_qty,
                currency=p.currency,
                image_url=image_url,
            )
        )
    return result


# ── GET /store/products/{product_id} ──────────────────────────────────────────


@router.get(
    "/products/{product_id}",
    response_model=StorefrontProductDetail,
    summary="Get a single published product's full detail",
)
async def get_product_detail(
    product_id: str,
    tenant_id: StorefrontTenantId,
    session: SessionDep,
) -> StorefrontProductDetail:
    await _check_mode_gate(tenant_id, session)
    repo = ProductRepository(session, tenant_id)
    product = await repo.get_by_id(product_id)

    if product is None or product.storefront_status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or not available.",
        )

    image_url: str | None = None
    if product.image_path:
        with contextlib.suppress(Exception):
            image_url = await get_presigned_url(tenant_id, product.image_path, expires_seconds=3600)

    return StorefrontProductDetail(
        product_id=product.product_id,
        product_name=product.product_name,
        description=product.description,
        retail_price=float(product.retail_price) if product.retail_price is not None else None,
        storefront_qty=product.storefront_qty,
        currency=product.currency,
        image_url=image_url,
        specifications=product.specifications,
        enrichment_source=product.enrichment_source,
    )


# ── POST /store/cart/validate ──────────────────────────────────────────────────


@router.post(
    "/cart/validate",
    response_model=CartValidationResponse,
    summary="Validate cart items: check published status and available storefront_qty",
)
async def validate_cart(
    body: CartValidationRequest,
    tenant_id: StorefrontTenantId,
    session: SessionDep,
) -> CartValidationResponse:
    await _check_mode_gate(tenant_id, session)
    repo = ProductRepository(session, tenant_id)
    errors: list[str] = []
    items: list[dict[str, Any]] = []

    for cart_item in body.items:
        product = await repo.get_by_id(cart_item.product_id)
        published = product is not None and product.storefront_status == "published"
        result = evaluate_cart_line(
            cart_item.product_id,
            exists_and_published=published,
            product_name=product.product_name if product is not None else "",
            available_qty=product.storefront_qty if product is not None else 0,
            requested_qty=cart_item.qty,
            unit_price=(
                float(product.retail_price)
                if product is not None and product.retail_price
                else 0.0
            ),
        )
        items.append(result.item)
        if result.error:
            errors.append(result.error)

    return CartValidationResponse(valid=len(errors) == 0, items=items, errors=errors)


# ── POST /store/checkout ───────────────────────────────────────────────────────


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate checkout: validate cart, create pending order + invoice, create payment intent",
)
async def checkout(
    body: CheckoutRequest,
    tenant_id: StorefrontTenantId,
    session: SessionDep,
) -> CheckoutResponse:
    """
    Checkout flow:
    1. Validate all items are published with sufficient storefront_qty
    2. Calculate total
    3. Create ConsumerOrder (status='pending_payment') + ConsumerOrderItems
    4. Create Invoice (receivable, b2c, unpaid)
    5. Create payment intent via selected gateway
    6. Return payment_details (Stripe: client_secret; OMT/Whish: redirect_url)

    storefront_qty is NOT decremented here — decremented atomically when payment
    webhook confirms payment (see POST /webhooks/stripe or POST /webhooks/omt).
    """
    await _check_mode_gate(tenant_id, session)

    if not body.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cart is empty.",
        )

    if body.payment_method not in {"stripe", "omt", "whish"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported payment method '{body.payment_method}'.",
        )

    product_repo = ProductRepository(session, tenant_id)
    order_repo = ConsumerOrderRepository(session, tenant_id)
    invoice_repo = InvoiceRepository(session, tenant_id)

    # ── Validate all items ─────────────────────────────────────────────────────
    validated: list[dict[str, Any]] = []
    for cart_item in body.items:
        product = await product_repo.get_by_id(cart_item.product_id)
        if product is None or product.storefront_status != "published":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product {cart_item.product_id} is no longer available.",
            )
        if product.storefront_qty < cart_item.qty:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock for '{product.product_name}': "
                    f"{product.storefront_qty} available, {cart_item.qty} requested."
                ),
            )
        validated.append({
            "product": product,
            "qty": cart_item.qty,
            "unit_price": float(product.retail_price) if product.retail_price else 0.0,
        })

    total = calculate_order_total([(v["unit_price"], v["qty"]) for v in validated])
    order_id = uuid.uuid4().hex
    invoice_id = uuid.uuid4().hex
    today = date.today()

    # ── Create order + items ───────────────────────────────────────────────────
    await order_repo.create(
        order_id=order_id,
        customer_id=body.consumer_email,
        payment_gateway=body.payment_method,
        total_amount=Decimal(str(total)),
        status="pending_payment",
    )
    for v in validated:
        await order_repo.add_item(
            item_id=uuid.uuid4().hex,
            order_id=order_id,
            product_id=v["product"].product_id,
            qty=v["qty"],
            unit_price=Decimal(str(v["unit_price"])),
        )

    # ── Create invoice ─────────────────────────────────────────────────────────
    from app.infra.db.models.dunning import Invoice  # noqa: PLC0415

    invoice = Invoice(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        direction="receivable",
        invoice_type="b2c",
        amount_due=total,
        invoice_date=today,
        due_date=today,
        payment_terms_days=0,
        currency=body.currency,
        status="unpaid",
        contact_email=body.consumer_email,
        contact_name=body.consumer_name,
        contact_language=body.language,
        order_id=order_id,
    )
    await invoice_repo.create(invoice)
    await session.commit()

    # ── Create payment intent ─────────────────────────────────────────────────
    gateway = _get_gateway(body.payment_method)
    try:
        payment_details = await gateway.create_payment_intent(
            amount=total,
            currency=body.currency,
            metadata={
                "tenant_id": tenant_id,
                "order_id": order_id,
                "invoice_id": invoice_id,
                "consumer_email": body.consumer_email,
            },
        )
    except Exception as exc:
        logger.error("payment_intent_failed", order_id=order_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment gateway error. Please try again.",
        ) from exc

    logger.info(
        "checkout_initiated",
        order_id=order_id,
        invoice_id=invoice_id,
        total=total,
        method=body.payment_method,
        tenant_id=tenant_id,
    )

    return CheckoutResponse(
        order_id=order_id,
        invoice_id=invoice_id,
        total_amount=total,
        currency=body.currency,
        payment_method=body.payment_method,
        payment_details=payment_details,
    )


# ── GET /store/orders/{order_id} ──────────────────────────────────────────────


@router.get(
    "/orders/{order_id}",
    response_model=OrderStatusResponse,
    summary="Get consumer order status (for order confirmation page)",
)
async def get_order_status(
    order_id: str,
    tenant_id: StorefrontTenantId,
    session: SessionDep,
) -> OrderStatusResponse:
    repo = ConsumerOrderRepository(session, tenant_id)
    order = await repo.get_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    return OrderStatusResponse(
        order_id=order.order_id,
        status=order.status,
        total_amount=float(order.total_amount),
        payment_gateway=order.payment_gateway,
        created_at=str(order.created_at),
    )
