"""
Feature:  Activity & Notifications (cross-cutting)
Layer:    Infra / Repository
Module:   app.infra.db.repos.notification_repo
Purpose:  Data access for the per-tenant event log + a `record_event` helper that
          callers use to log a real event when something happens (enrichment done,
          order created, PO sent, supplier reply, outreach sent). All queries are
          tenant-filtered.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.notification
HITL:     None — repository only.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update

from app.infra.db.models.notification import Notification
from app.infra.db.repos.base_repo import TenantRepository


class NotificationRepository(TenantRepository):
    async def add(
        self, *, kind: str, title: str, body: str | None = None, link: str | None = None
    ) -> Notification:
        n = Notification(
            notification_id=uuid.uuid4().hex,
            tenant_id=self._tenant_id,
            kind=kind,
            title=title,
            body=body,
            link=link,
        )
        self._session.add(n)
        await self._session.flush()
        return n

    async def list_recent(self, limit: int = 100, kind: str | None = None) -> list[Notification]:
        q = select(Notification).where(self._tenant_filter(Notification))
        if kind and kind != "all":
            q = q.where(Notification.kind == kind)
        q = q.order_by(Notification.created_at.desc()).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def unread_count(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(self._tenant_filter(Notification), Notification.read_at.is_(None))
        )
        return int(result.scalar_one())

    async def mark_read(self, notification_id: str) -> None:
        await self._session.execute(
            update(Notification)
            .where(self._tenant_filter(Notification), Notification.notification_id == notification_id)
            .values(read_at=func.now())
        )

    async def mark_all_read(self) -> None:
        await self._session.execute(
            update(Notification)
            .where(self._tenant_filter(Notification), Notification.read_at.is_(None))
            .values(read_at=func.now())
        )


async def record_event(
    session: object,
    tenant_id: str,
    *,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> None:
    """Best-effort: log a real event to the per-tenant activity feed. Never raises —
    a notification failure must not break the action that triggered it."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415

        if not isinstance(session, AsyncSession):
            return
        repo = NotificationRepository(session, tenant_id)
        await repo.add(kind=kind, title=title, body=body, link=link)
    except Exception:  # noqa: BLE001 — notifications are non-critical
        import structlog  # noqa: PLC0415

        structlog.get_logger(__name__).warning("notification_record_failed", kind=kind)
