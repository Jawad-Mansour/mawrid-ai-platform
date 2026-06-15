"""
Feature:  Supplier Intelligence
Layer:    API / Router
Module:   app.api.suppliers
Purpose:  HTTP routes for supplier CRUD, matching waterfall, delivery event
          recording, score retrieval, supplier discovery, and reorder signal.
          POST /suppliers/{id}/delivery-event records a delivery then immediately
          recomputes the supplier score.
          POST /suppliers/match runs the 5-step matching waterfall.
          POST /suppliers/reorder-check triggers the reorder signal for all
          products below threshold.
Depends:  app.core.suppliers.services, app.infra.db.repos.supplier_repo, app.api.deps
HITL:     supplier_match_review, supplier_outreach, purchase_order_send (reorder)
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.core.suppliers.models import DeliveryEventInput, SupplierMatchResult
from app.core.suppliers.services import (
    discover_suppliers,
    get_supplier_score,
    match_supplier,
    record_delivery_event,
    trigger_reorder_check,
)
from app.infra.db.repos.supplier_repo import SupplierRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class SupplierCreate(StrictModel):
    name: str
    email: str | None = None
    phone: str | None = None
    language: str = "en"
    currency: str = "USD"


class SupplierUpdate(StrictModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    language: str | None = None
    currency: str | None = None


class SupplierMatchRequest(StrictModel):
    name: str
    embedding: list[float] | None = None


class DiscoverRequest(StrictModel):
    product_name: str
    category: str


class SupplierResponse(StrictModel):
    supplier_id: str
    name: str
    email: str | None
    phone: str | None
    language: str
    currency: str
    score: float | None


class ScoreResponse(StrictModel):
    supplier_id: str
    score: float
    method: str
    sample_count: int
    features: dict[str, float]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new supplier",
)
async def create_supplier(
    body: SupplierCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> SupplierResponse:
    repo = SupplierRepository(session, current_user.tenant_id)
    supplier = await repo.create(
        supplier_id=uuid.uuid4().hex,
        name=body.name,
        email=body.email,
        phone=body.phone,
        language=body.language,
        currency=body.currency,
    )
    await session.commit()
    logger.info("supplier_created", supplier_id=supplier.supplier_id, name=supplier.name)
    return SupplierResponse(
        supplier_id=supplier.supplier_id,
        name=supplier.name,
        email=supplier.email,
        phone=supplier.phone,
        language=supplier.language,
        currency=supplier.currency,
        score=float(supplier.score) if supplier.score is not None else None,
    )


@router.get(
    "",
    response_model=list[SupplierResponse],
    summary="List all suppliers for the tenant",
)
async def list_suppliers(
    current_user: CurrentUser,
    session: SessionDep,
) -> list[SupplierResponse]:
    repo = SupplierRepository(session, current_user.tenant_id)
    suppliers = await repo.list_all()
    return [
        SupplierResponse(
            supplier_id=s.supplier_id,
            name=s.name,
            email=s.email,
            phone=s.phone,
            language=s.language,
            currency=s.currency,
            score=float(s.score) if s.score is not None else None,
        )
        for s in suppliers
    ]


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier detail",
)
async def get_supplier(
    supplier_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> SupplierResponse:
    repo = SupplierRepository(session, current_user.tenant_id)
    supplier = await repo.get_by_id(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")
    return SupplierResponse(
        supplier_id=supplier.supplier_id,
        name=supplier.name,
        email=supplier.email,
        phone=supplier.phone,
        language=supplier.language,
        currency=supplier.currency,
        score=float(supplier.score) if supplier.score is not None else None,
    )


@router.put(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Update supplier contact info and language",
)
async def update_supplier(
    supplier_id: str,
    body: SupplierUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> SupplierResponse:
    repo = SupplierRepository(session, current_user.tenant_id)
    supplier = await repo.get_by_id(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found.")

    updates: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await repo.update(supplier_id, **updates)
    await session.commit()

    updated = await repo.get_by_id(supplier_id)
    assert updated is not None
    return SupplierResponse(
        supplier_id=updated.supplier_id,
        name=updated.name,
        email=updated.email,
        phone=updated.phone,
        language=updated.language,
        currency=updated.currency,
        score=float(updated.score) if updated.score is not None else None,
    )


@router.post(
    "/match",
    response_model=SupplierMatchResult,
    summary="Run supplier matching waterfall (exact → TF-IDF → embedding → HITL → new?)",
)
async def match_supplier_endpoint(
    body: SupplierMatchRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> SupplierMatchResult:
    """
    Attempts to match the given name against existing suppliers:
    1. Exact name → auto-link (confidence 1.0)
    2. TF-IDF char n-gram ≥ 0.9 → auto-link
    3. Embedding cosine ≥ 0.9 → auto-link (if embedding provided)
    4. Best similarity 0.3–0.9 → HITL supplier_match_review
    5. All < 0.3 → HITL "create new supplier?" prompt
    """
    result = await match_supplier(
        session=session,
        tenant_id=current_user.tenant_id,
        name=body.name,
        embedding=body.embedding,
    )
    if result.match_type != "hitl":
        await session.commit()
    return result


@router.post(
    "/{supplier_id}/delivery-event",
    response_model=ScoreResponse,
    summary="Record a delivery event and recompute supplier score",
)
async def add_delivery_event(
    supplier_id: str,
    body: DeliveryEventInput,
    current_user: CurrentUser,
    session: SessionDep,
) -> ScoreResponse:
    """
    Records one delivery performance event and immediately recomputes the supplier
    score using the Ridge regression model (or formula fallback).
    Called after goods-receiving to keep scores current.
    """
    try:
        result = await record_delivery_event(
            session=session,
            tenant_id=current_user.tenant_id,
            supplier_id=supplier_id,
            event_in=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    f = result.features
    return ScoreResponse(
        supplier_id=supplier_id,
        score=result.score,
        method=result.method,
        sample_count=result.sample_count,
        features={
            "on_time_delivery_rate": f.on_time_delivery_rate,
            "damage_rate": f.damage_rate,
            "avg_price_vs_market": f.avg_price_vs_market,
            "response_time_hours": f.response_time_hours,
            "discrepancy_rate": f.discrepancy_rate,
            "catalog_completeness": f.catalog_completeness,
        },
    )


@router.get(
    "/{supplier_id}/score",
    response_model=ScoreResponse,
    summary="Get current supplier score with feature breakdown",
)
async def get_score(
    supplier_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> ScoreResponse:
    try:
        result = await get_supplier_score(
            session=session,
            tenant_id=current_user.tenant_id,
            supplier_id=supplier_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    f = result.features
    return ScoreResponse(
        supplier_id=supplier_id,
        score=result.score,
        method=result.method,
        sample_count=result.sample_count,
        features={
            "on_time_delivery_rate": f.on_time_delivery_rate,
            "damage_rate": f.damage_rate,
            "avg_price_vs_market": f.avg_price_vs_market,
            "response_time_hours": f.response_time_hours,
            "discrepancy_rate": f.discrepancy_rate,
            "catalog_completeness": f.catalog_completeness,
        },
    )


@router.post(
    "/reorder-check",
    summary="Trigger reorder signal for all products below threshold",
)
async def reorder_check(
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """
    Checks all products where qty_in_stock ≤ reorder_threshold.
    For each: selects best-scored supplier, drafts PO via GPT-4o, creates
    HITL purchase_order_send action.
    Guard: skips products that already have a pending PO HITL action.
    """
    action_ids = await trigger_reorder_check(
        session=session,
        tenant_id=current_user.tenant_id,
    )
    await session.commit()
    return {"actions_created": len(action_ids), "action_ids": action_ids}


@router.post(
    "/discover",
    summary="Discover potential new suppliers via web search (SearXNG)",
)
async def discover(
    body: DiscoverRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, object]:
    """
    Searches SearXNG for '{product_name} {category} wholesale supplier distributor',
    drafts outreach emails for up to 3 candidates via GPT-4o, and creates a HITL
    supplier_outreach action for each. No email is sent without importer approval.
    """
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    searxng_url = settings.searxng_base_url
    action_ids = await discover_suppliers(
        session=session,
        tenant_id=current_user.tenant_id,
        product_name=body.product_name,
        category=body.category,
        searxng_url=str(searxng_url),
    )
    await session.commit()
    return {"actions_created": len(action_ids), "action_ids": action_ids}
