"""
Feature:  Authentication & Tenant Onboarding
Layer:    Infra / DB Repos
Module:   app.infra.db.repos.tenant_repo
Purpose:  Database access for tenant provisioning and user management.
          TenantRepo creates/fetches tenants (no tenant_id filter — tenants
          ARE the root). UserRepo creates and looks up users by email or ID.
Depends:  app.infra.db.models.tenant, sqlalchemy
HITL:     None — repository only.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.tenant import Tenant, User


class TenantRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant_id: str, name: str, mode: str) -> Tenant:
        tenant = Tenant(tenant_id=tenant_id, name=name, mode=mode)
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
        return result.scalar_one_or_none()

    async def list_active_tenant_ids(self) -> list[str]:
        """Return all active tenant IDs — used by scheduler to run per-tenant dunning jobs."""
        result = await self._session.execute(
            select(Tenant.tenant_id).where(Tenant.is_active.is_(True))
        )
        return list(result.scalars().all())


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        password_hash: str,
        role: str = "admin",
    ) -> User:
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()
