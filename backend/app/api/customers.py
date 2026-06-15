"""
Feature:  Customer Management
Layer:    API / Router
Module:   app.api.customers
Purpose:  HTTP routes for customer CRUD, matching waterfall, segment assignment,
          and payment history score updates. The /match endpoint runs the full
          5-step waterfall (email → phone → TF-IDF → HITL → auto-create).
Depends:  app.core.customers.services, app.api.deps
HITL:     customer_match_review
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import update as sa_update

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.core.customers.models import CustomerMatchResult
from app.core.customers.services import (
    match_or_create_customer,
    record_payment_outcome,
    update_segment,
)
from app.infra.db.models.customer import Customer
from app.infra.db.repos.customer_repo import CustomerRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class CustomerCreate(StrictModel):
    customer_id: str | None = None
    name: str
    customer_type: str
    email: str | None = None
    phone: str | None = None
    language: str = "en"
    segment: str = "Regular"


class CustomerUpdate(StrictModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    language: str | None = None
    segment: str | None = None


class CustomerMatchRequest(StrictModel):
    name: str
    customer_type: str
    email: str | None = None
    phone: str | None = None


class PaymentOutcomeRequest(StrictModel):
    outcome: float  # 1.0 on time | 0.5 late | 0.0 after dunning


class CustomerResponse(StrictModel):
    customer_id: str
    name: str
    customer_type: str
    email: str | None
    phone: str | None
    segment: str
    language: str
    payment_history_score: float
    previous_dunning_count: int


# ── Helpers ────────────────────────────────────────────────────────────────────


def _to_response(c: Customer) -> CustomerResponse:
    return CustomerResponse(
        customer_id=c.customer_id,
        name=c.name,
        customer_type=c.customer_type,
        email=c.email,
        phone=c.phone,
        segment=c.segment,
        language=c.language,
        payment_history_score=float(c.payment_history_score),
        previous_dunning_count=c.previous_dunning_count,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer record directly (use /match for deduplication)",
)
async def create_customer(
    body: CustomerCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> CustomerResponse:
    import uuid  # noqa: PLC0415

    repo = CustomerRepository(session, current_user.tenant_id)
    if body.email:
        existing = await repo.get_by_email(body.email)
        if existing:
            return _to_response(existing)

    customer_id = body.customer_id or str(uuid.uuid4())
    customer = Customer(
        customer_id=customer_id,
        tenant_id=current_user.tenant_id,
        name=body.name,
        customer_type=body.customer_type,
        email=body.email,
        phone=body.phone,
        language=body.language,
        segment=body.segment,
    )
    created = await repo.create(customer)
    await session.commit()
    logger.info("customer_created_api", tenant_id=current_user.tenant_id, customer_id=customer_id)
    return _to_response(created)


@router.get(
    "",
    response_model=list[CustomerResponse],
    summary="List all customers for this tenant",
)
async def list_customers(
    current_user: CurrentUser,
    session: SessionDep,
    limit: int = 100,
) -> list[CustomerResponse]:
    repo = CustomerRepository(session, current_user.tenant_id)
    customers = await repo.list_all(limit=limit)
    return [_to_response(c) for c in customers]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get a single customer by ID",
)
async def get_customer(
    customer_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> CustomerResponse:
    repo = CustomerRepository(session, current_user.tenant_id)
    customer = await repo.get_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return _to_response(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer contact info, segment, or language",
)
async def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> CustomerResponse:
    repo = CustomerRepository(session, current_user.tenant_id)
    customer = await repo.get_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.email is not None:
        updates["email"] = body.email
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.language is not None:
        updates["language"] = body.language
    if body.segment is not None:
        updates["segment"] = body.segment

    if updates:
        await session.execute(
            sa_update(Customer)
            .where(
                Customer.tenant_id == current_user.tenant_id,
                Customer.customer_id == customer_id,
            )
            .values(**updates)
        )
        await session.commit()
        customer = await repo.get_by_id(customer_id)

    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return _to_response(customer)


@router.post(
    "/match",
    response_model=CustomerMatchResult,
    summary="Run customer deduplication waterfall (email → phone → TF-IDF → HITL → create)",
)
async def match_customer(
    body: CustomerMatchRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> CustomerMatchResult:
    """
    Waterfall:
    1. Exact email → auto-link (confidence 1.0)
    2. Exact phone → auto-link (confidence 0.95)
    3. TF-IDF name ≥ 0.85 → auto-link
    4. TF-IDF name 0.3–0.85 → HITL customer_match_review (hitl_action_id returned, no customer_id)
    5. < 0.3 → auto-create new customer record
    """
    result = await match_or_create_customer(
        session=session,
        tenant_id=current_user.tenant_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        customer_type=body.customer_type,
    )
    if result.match_type != "hitl":
        await session.commit()
    return result


@router.put(
    "/{customer_id}/segment",
    summary="Manually assign a customer segment (VIP / Regular / At-Risk / Dormant)",
)
async def set_segment(
    customer_id: str,
    body: dict[str, str],
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    segment = body.get("segment", "")
    valid = {"VIP", "Regular", "At-Risk", "Dormant"}
    if segment not in valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"segment must be one of {sorted(valid)}",
        )
    await update_segment(session, current_user.tenant_id, customer_id, segment)
    await session.commit()
    return {"customer_id": customer_id, "segment": segment}


@router.post(
    "/{customer_id}/payment-outcome",
    summary="Record a payment outcome and update rolling payment_history_score",
)
async def record_payment(
    customer_id: str,
    body: PaymentOutcomeRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str | float]:
    """outcome: 1.0 = on time, 0.5 = late before dunning, 0.0 = after dunning."""
    if not 0.0 <= body.outcome <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="outcome must be between 0.0 and 1.0",
        )
    new_score = await record_payment_outcome(
        session, current_user.tenant_id, customer_id, body.outcome
    )
    await session.commit()
    return {"customer_id": customer_id, "payment_history_score": new_score}
