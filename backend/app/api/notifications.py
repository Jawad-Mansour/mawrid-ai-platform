"""
Feature:  Activity & Notifications (cross-cutting)
Layer:    API / Router
Module:   app.api.notifications
Purpose:  HTTP routes for the per-tenant Activity feed: list recent events,
          unread count (badge), mark one/all read.
Depends:  app.infra.db.repos.notification_repo, app.api.deps
HITL:     None.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import StrictModel
from app.infra.db.repos.notification_repo import NotificationRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationItem(StrictModel):
    notification_id: str
    kind: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: str


class NotificationsResponse(StrictModel):
    items: list[NotificationItem]
    unread: int


@router.get("", response_model=NotificationsResponse, summary="List recent activity events")
async def list_notifications(
    current_user: CurrentUser,
    session: SessionDep,
    kind: str | None = None,
    limit: int = 100,
) -> NotificationsResponse:
    repo = NotificationRepository(session, current_user.tenant_id)
    rows = await repo.list_recent(limit=limit, kind=kind)
    unread = await repo.unread_count()
    return NotificationsResponse(
        items=[
            NotificationItem(
                notification_id=n.notification_id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                link=n.link,
                read=n.read_at is not None,
                created_at=str(n.created_at),
            )
            for n in rows
        ],
        unread=unread,
    )


@router.post("/{notification_id}/read", summary="Mark one notification read")
async def mark_read(
    notification_id: str, current_user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    repo = NotificationRepository(session, current_user.tenant_id)
    await repo.mark_read(notification_id)
    await session.commit()
    return {"status": "ok"}


@router.post("/read-all", summary="Mark all notifications read")
async def mark_all_read(current_user: CurrentUser, session: SessionDep) -> dict[str, str]:
    repo = NotificationRepository(session, current_user.tenant_id)
    await repo.mark_all_read()
    await session.commit()
    return {"status": "ok"}
