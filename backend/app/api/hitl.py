"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    API / Router
Module:   app.api.hitl
Purpose:  HTTP routes for listing pending HITL actions, approve (A shortcut),
          reject (R shortcut), edit payload (E shortcut), and history view.
          This is the single approval surface for ALL action_types.
Depends:  app.core.hitl.services, app.infra.db.repos.hitl_repo, app.api.deps
HITL:     This IS the HITL surface — all 14 action_types route through here.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.email.sender import EmailSender

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/hitl", tags=["hitl"])


# ── Response schemas ───────────────────────────────────────────────────────────


class HITLActionResponse(StrictModel):
    action_id: str
    action_type: str
    status: str
    payload: dict[str, Any]
    created_at: str
    expires_at: str | None


class EditPayloadRequest(StrictModel):
    payload: dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/actions",
    response_model=list[HITLActionResponse],
    summary="List pending HITL actions for the tenant",
)
async def list_hitl_actions(
    current_user: CurrentUser,
    session: SessionDep,
    action_type: str | None = None,
    all_statuses: bool = False,
) -> list[HITLActionResponse]:
    repo = HITLRepository(session, current_user.tenant_id)
    if all_statuses:
        actions = await repo.list_all()
    else:
        actions = await repo.list_pending(action_type=action_type)
    return [
        HITLActionResponse(
            action_id=a.action_id,
            action_type=a.action_type,
            status=a.status,
            payload=a.payload,
            created_at=str(a.created_at),
            expires_at=str(a.expires_at) if a.expires_at else None,
        )
        for a in actions
    ]


@router.get(
    "/actions/{action_id}",
    response_model=HITLActionResponse,
    summary="Get a single HITL action",
)
async def get_hitl_action(
    action_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> HITLActionResponse:
    repo = HITLRepository(session, current_user.tenant_id)
    action = await repo.get_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")
    return HITLActionResponse(
        action_id=action.action_id,
        action_type=action.action_type,
        status=action.status,
        payload=action.payload,
        created_at=str(action.created_at),
        expires_at=str(action.expires_at) if action.expires_at else None,
    )


@router.post(
    "/actions/{action_id}/approve",
    summary="Approve a HITL action (A shortcut). Triggers external write.",
)
async def approve_hitl_action(
    action_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    repo = HITLRepository(session, current_user.tenant_id)
    action = await repo.get_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")
    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action is not pending (current: {action.status}).",
        )

    from app.core.hitl.services import approve_action

    email_sender = EmailSender()
    result = await approve_action(
        action_id=action_id,
        action_type=action.action_type,
        payload=action.payload,
        email_sender=email_sender,
    )

    await repo.set_status(action_id, result.status, actor_user_id=current_user.user_id)
    await session.commit()

    logger.info(
        "hitl_approved",
        action_id=action_id,
        action_type=action.action_type,
        user_id=current_user.user_id,
    )

    # Notify n8n when a PO is approved so WF-04 can create the shipment record
    if action.action_type == "purchase_order_send":
        # Mark the PO sent and log the outbound message in its thread (Screen 3).
        po_id = action.payload.get("po_id")
        if po_id and result.status == "approved":
            from datetime import UTC, datetime  # noqa: PLC0415

            from app.infra.db.repos.order_repo import OrderRepository  # noqa: PLC0415

            order_repo = OrderRepository(session, current_user.tenant_id)
            await order_repo.mark_po_sent(
                str(po_id),
                {
                    "direction": "outbound",
                    "sender": "You",
                    "body": str(action.payload.get("body", "")),
                    "at": datetime.now(UTC).isoformat(),
                },
            )
            await session.commit()

        from app.infra.n8n.client import fire_event  # noqa: PLC0415

        background_tasks.add_task(
            fire_event,
            "wf04-po-approved",
            {
                "tenant_id": current_user.tenant_id,
                "action_id": action_id,
                "payload": action.payload,
            },
        )

    return {"action_id": action_id, "status": result.status}


@router.post(
    "/actions/{action_id}/reject",
    summary="Reject a HITL action (R shortcut). No external write.",
)
async def reject_hitl_action(
    action_id: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    repo = HITLRepository(session, current_user.tenant_id)
    action = await repo.get_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")
    if action.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action is not pending (current: {action.status}).",
        )

    from app.core.hitl.services import reject_action

    result = reject_action(action_id=action_id, action_type=action.action_type)
    await repo.set_status(action_id, result.status, actor_user_id=current_user.user_id)
    await session.commit()

    logger.info("hitl_rejected", action_id=action_id)
    return {"action_id": action_id, "status": result.status}


@router.put(
    "/actions/{action_id}",
    summary="Edit a HITL action payload (E shortcut). Returns to pending.",
)
async def edit_hitl_action(
    action_id: str,
    body: EditPayloadRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    repo = HITLRepository(session, current_user.tenant_id)
    action = await repo.get_by_id(action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found.")

    from app.core.hitl.services import edit_action

    result = edit_action(action_id=action_id, updates=body.payload)
    await repo.update_payload(action_id, result.payload)
    await session.commit()

    logger.info("hitl_edited", action_id=action_id)
    return {"action_id": action_id, "status": result.status}
