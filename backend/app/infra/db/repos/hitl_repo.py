"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Infra / Repository
Module:   app.infra.db.repos.hitl_repo
Purpose:  Data access for hitl_actions table: create, status transitions,
          list pending by action_type, expire stale actions, bulk cancel
          by invoice_id (payment auto-stop). All queries include tenant_id filter.
Depends:  app.infra.db.repos.base_repo, app.infra.db.models.hitl
HITL:     This IS the HITL data layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.infra.db.models.hitl import HITLAction
from app.infra.db.repos.base_repo import TenantRepository


class HITLRepository(TenantRepository):
    async def create(
        self,
        action_id: str,
        action_type: str,
        payload: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> HITLAction:
        action = HITLAction(
            action_id=action_id,
            tenant_id=self._tenant_id,
            action_type=action_type,
            status="pending",
            payload=payload,
            expires_at=expires_at,
        )
        self._session.add(action)
        await self._session.flush()
        return action

    async def get_by_id(self, action_id: str) -> HITLAction | None:
        result = await self._session.execute(
            select(HITLAction).where(
                self._tenant_filter(HITLAction),
                HITLAction.action_id == action_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending(self, action_type: str | None = None) -> list[HITLAction]:
        q = select(HITLAction).where(
            self._tenant_filter(HITLAction),
            HITLAction.status == "pending",
        )
        if action_type:
            q = q.where(HITLAction.action_type == action_type)
        q = q.order_by(HITLAction.created_at)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_all(self, limit: int = 100) -> list[HITLAction]:
        result = await self._session.execute(
            select(HITLAction)
            .where(self._tenant_filter(HITLAction))
            .order_by(HITLAction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def set_status(
        self,
        action_id: str,
        new_status: str,
        actor_user_id: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": new_status}
        if actor_user_id:
            values["actor_user_id"] = actor_user_id
        await self._session.execute(
            update(HITLAction)
            .where(
                self._tenant_filter(HITLAction),
                HITLAction.action_id == action_id,
            )
            .values(**values)
        )

    async def update_payload(self, action_id: str, payload: dict[str, Any]) -> None:
        await self._session.execute(
            update(HITLAction)
            .where(
                self._tenant_filter(HITLAction),
                HITLAction.action_id == action_id,
            )
            .values(payload=payload, status="pending")
        )

    async def expire_stale(self) -> int:
        """Mark all pending actions past their expires_at as expired. Returns count."""
        now = datetime.now(UTC)
        result = await self._session.execute(
            update(HITLAction)
            .where(
                self._tenant_filter(HITLAction),
                HITLAction.status == "pending",
                HITLAction.expires_at.isnot(None),
                HITLAction.expires_at < now,
            )
            .values(status="expired")
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def bulk_cancel_by_invoice(self, invoice_id: str) -> int:
        """
        Cancel all pending HITL actions whose payload.invoice_id == invoice_id.
        Used by payment auto-stop to atomically clean up the dunning queue.
        Returns count of cancelled actions.
        """
        result = await self._session.execute(
            update(HITLAction)
            .where(
                self._tenant_filter(HITLAction),
                HITLAction.status == "pending",
                HITLAction.payload["invoice_id"].as_string() == invoice_id,
            )
            .values(status="rejected")
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
