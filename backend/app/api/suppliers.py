"""
Feature:  Supplier Intelligence
Layer:    API / Router
Module:   app.api.suppliers
Purpose:  HTTP routes for supplier CRUD. Supplier language drives PO language
          and dunning message language. Phase 7 extends this with scoring and
          matching waterfall endpoints.
Depends:  app.infra.db.repos.supplier_repo, app.api.deps
HITL:     supplier_outreach (Phase 7), supplier_match_review (Phase 7)
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.infra.db.repos.supplier_repo import SupplierRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class SupplierCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    language: str = "en"
    currency: str = "USD"


class SupplierUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    language: str | None = None
    currency: str | None = None


class SupplierResponse(BaseModel):
    supplier_id: str
    name: str
    email: str | None
    phone: str | None
    language: str
    currency: str
    score: float | None


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

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await repo.update(supplier_id, **updates)
    await session.commit()

    # Re-fetch to return updated values
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
