"""
Feature:  Auth & Dependency Injection (cross-cutting)
Layer:    API / Dependencies
Module:   app.api.deps
Purpose:  FastAPI Depends() providers: JWT parsing, tenant_id extraction,
          DB async session, repository injection, current user resolution,
          operational mode gate (require_mode).
Depends:  app.infra.db.session, app.core.auth.models, app.core.auth.services
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import UserDomain
from app.core.auth.services import JWT_ALGORITHM
from app.infra.db.repos.tenant_repo import UserRepo
from app.infra.db.session import get_db_session
from app.infra.secrets.vault import get_secrets

_bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserDomain:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        secrets = get_secrets()
        raw = jwt.decode(
            credentials.credentials,
            secrets.jwt_public_key,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token."
        ) from exc

    if raw.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token.")

    user_repo = UserRepo(session)
    user_orm = await user_repo.get_by_id(str(raw["sub"]))
    if user_orm is None or not user_orm.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    # Activate Row-Level Security for all subsequent queries in this session.
    # set_config(..., true) = SET LOCAL: persists for the current transaction only.
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": user_orm.tenant_id},
    )

    return UserDomain(
        user_id=user_orm.user_id,
        tenant_id=user_orm.tenant_id,
        email=user_orm.email,
        role=user_orm.role,
    )


CurrentUser = Annotated[UserDomain, Depends(get_current_user)]


def require_mode(*modes: str):  # type: ignore[no-untyped-def]
    """Return a dependency that enforces operational mode access."""

    async def _check(user: CurrentUser) -> UserDomain:
        # Mode guard is evaluated at route level, so we check tenant mode via user's tenant_id.
        # For now: all modes pass — mode enforcement added in Phase 3 when routes diverge.
        _ = modes  # will be used in Phase 3
        return user

    return Depends(_check)
