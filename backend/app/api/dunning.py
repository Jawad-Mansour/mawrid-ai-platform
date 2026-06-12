"""
Feature:  Dunning Engine (4 Tracks)
Layer:    API / Router
Module:   app.api.dunning
Purpose:  HTTP routes for dunning sequence management and manual triggers.
          Scheduled triggers (Track 1, 3, 4) are fired by APScheduler.
          Track 2 (disputes) is always on-demand via this API.
          Mode gate on Track 2: Hybrid + Wholesale Only only.
Depends:  app.core.dunning.services, app.api.deps
HITL:     All dunning action_types routed through this module.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep, require_mode
from app.infra.db.repos.dunning_repo import DunningRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dunning", tags=["dunning"])


# ── Request / response schemas ─────────────────────────────────────────────────


class DisputeRequest(BaseModel):
    invoice_id: str
    supplier_id: str
    po_reference: str
    shipment_id: str
    dispute_type: str  # damaged | shortage | wrong_item | other
    products_affected_json: str  # JSON array string
    damage_description: str
    resolution_requested: str  # replacement | credit_note | refund


class DunningSequenceResponse(BaseModel):
    sequence_id: str
    invoice_id: str
    track: str
    status: str
    created_at: str
    stopped_at: str | None


class TriggerResponse(BaseModel):
    actions_created: int
    action_ids: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/disputes",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="File a supplier dispute (Track 2) — Hybrid/Wholesale Only",
    dependencies=[require_mode("hybrid", "wholesale_only")],
)
async def file_dispute(
    body: DisputeRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> TriggerResponse:
    """
    On-demand dispute letter. Drafts a formal complaint to the supplier via GPT-4o
    and creates a HITL action. Importer approves (A), rejects (R), or edits (E)
    before the letter is sent.
    """
    from app.core.dunning.services import trigger_track2  # noqa: PLC0415

    try:
        action_id = await trigger_track2(
            session=session,
            tenant_id=current_user.tenant_id,
            invoice_id=body.invoice_id,
            supplier_id=body.supplier_id,
            dispute_context={
                "po_reference": body.po_reference,
                "shipment_id": body.shipment_id,
                "dispute_type": body.dispute_type,
                "products_affected_json": body.products_affected_json,
                "damage_description": body.damage_description,
                "resolution_requested": body.resolution_requested,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await session.commit()
    logger.info(
        "dispute_filed",
        action_id=action_id,
        invoice_id=body.invoice_id,
        tenant_id=current_user.tenant_id,
    )
    return TriggerResponse(actions_created=1, action_ids=[action_id])


@router.post(
    "/trigger/track1",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually fire Track 1 (payables advance) for today",
)
async def manual_trigger_track1(
    current_user: CurrentUser,
    session: SessionDep,
) -> TriggerResponse:
    """Manual trigger for Track 1 (payables advance reminder). Used for testing."""
    from app.core.dunning.services import trigger_track1  # noqa: PLC0415

    action_ids = await trigger_track1(
        session=session,
        tenant_id=current_user.tenant_id,
        today=date.today(),
    )
    await session.commit()
    return TriggerResponse(actions_created=len(action_ids), action_ids=action_ids)


@router.post(
    "/trigger/track3",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually fire Track 3 (B2B receivables) for today",
)
async def manual_trigger_track3(
    current_user: CurrentUser,
    session: SessionDep,
) -> TriggerResponse:
    """Manual trigger for Track 3 (B2B receivables). Used for testing."""
    from app.core.dunning.services import trigger_track3  # noqa: PLC0415

    action_ids = await trigger_track3(
        session=session,
        tenant_id=current_user.tenant_id,
        today=date.today(),
    )
    await session.commit()
    return TriggerResponse(actions_created=len(action_ids), action_ids=action_ids)


@router.post(
    "/trigger/track4",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually fire Track 4 (B2C collections) for today",
)
async def manual_trigger_track4(
    current_user: CurrentUser,
    session: SessionDep,
) -> TriggerResponse:
    """Manual trigger for Track 4 (B2C collections). Used for testing."""
    from app.core.dunning.services import trigger_track4  # noqa: PLC0415

    action_ids = await trigger_track4(
        session=session,
        tenant_id=current_user.tenant_id,
        today=date.today(),
    )
    await session.commit()
    return TriggerResponse(actions_created=len(action_ids), action_ids=action_ids)


@router.get(
    "/sequences",
    response_model=list[DunningSequenceResponse],
    summary="List dunning sequences for the tenant",
)
async def list_dunning_sequences(
    current_user: CurrentUser,
    session: SessionDep,
    track: str | None = None,
    active_only: bool = True,
) -> list[DunningSequenceResponse]:
    repo = DunningRepository(session, current_user.tenant_id)
    if active_only:
        sequences = await repo.list_active(track=track)
    else:
        from sqlalchemy import select  # noqa: PLC0415

        from app.infra.db.models.dunning import DunningSequence  # noqa: PLC0415

        q = select(DunningSequence).where(
            repo._tenant_filter(DunningSequence)
        ).order_by(DunningSequence.created_at.desc()).limit(200)
        if track:
            q = q.where(DunningSequence.track == track)
        result = await session.execute(q)
        sequences = list(result.scalars().all())

    return [
        DunningSequenceResponse(
            sequence_id=s.sequence_id,
            invoice_id=s.invoice_id,
            track=s.track,
            status=s.status,
            created_at=s.created_at.isoformat(),
            stopped_at=s.stopped_at.isoformat() if s.stopped_at else None,
        )
        for s in sequences
    ]


@router.get(
    "/sequences/invoice/{invoice_id}",
    response_model=list[DunningSequenceResponse],
    summary="List all dunning sequences for a specific invoice",
)
async def list_invoice_sequences(
    invoice_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[DunningSequenceResponse]:
    repo = DunningRepository(session, current_user.tenant_id)
    sequences = await repo.list_by_invoice(invoice_id)
    return [
        DunningSequenceResponse(
            sequence_id=s.sequence_id,
            invoice_id=s.invoice_id,
            track=s.track,
            status=s.status,
            created_at=s.created_at.isoformat(),
            stopped_at=s.stopped_at.isoformat() if s.stopped_at else None,
        )
        for s in sequences
    ]


@router.post(
    "/sequences/{sequence_id}/stop",
    summary="Manually stop a dunning sequence",
)
async def stop_dunning_sequence(
    sequence_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    repo = DunningRepository(session, current_user.tenant_id)
    await repo.stop_sequence(sequence_id)
    await session.commit()
    logger.info("sequence_stopped_manually", sequence_id=sequence_id)
    return {"sequence_id": sequence_id, "status": "stopped"}


@router.get(
    "/tone/classify",
    summary="Preview tone classifier output for given features (diagnostic endpoint)",
)
async def classify_tone(
    days_overdue: int,
    customer_segment: str,
    overdue_amount: float,
    payment_history_score: float,
    previous_dunning_count: int,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Returns what tone the classifier would pick for the given features."""
    from app.ml.tone.classifier import classify  # noqa: PLC0415

    result = classify(
        days_overdue=days_overdue,
        customer_segment=customer_segment,
        overdue_amount=overdue_amount,
        payment_history_score=payment_history_score,
        previous_dunning_count=previous_dunning_count,
    )
    return {
        "tone": str(result.tone),
        "confidence": result.confidence,
        "features": result.features,
    }
