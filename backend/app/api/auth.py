"""
Feature:  Authentication & Tenant Onboarding
Layer:    API / Router
Module:   app.api.auth
Purpose:  HTTP routes for tenant self-signup, user login, JWT issuance,
          token refresh, and /auth/me (returns user + operational_mode).
          Triggers tenant provisioning workflow (n8n WF-01) on signup.
Depends:  app.core.auth.services, app.api.deps
HITL:     None — auth is not an external write action.
"""

from __future__ import annotations

import json
from typing import Any

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from app.api.deps import CurrentUser, SessionDep
from app.core.auth import services as auth_svc
from app.core.auth.models import OperationalMode
from app.infra.db.repos.tenant_repo import TenantRepo, UserRepo
from app.infra.secrets.vault import get_secrets

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    mode: OperationalMode = OperationalMode.HYBRID


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, response: Response, session: SessionDep) -> TokenResponse:
    secrets = get_secrets()
    tenant_repo = TenantRepo(session)
    user_repo = UserRepo(session)

    try:
        _, user = await auth_svc.signup(
            company_name=body.company_name,
            email=str(body.email),
            password=body.password,
            mode=body.mode.value,
            tenant_repo=tenant_repo,
            user_repo=user_repo,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await session.commit()

    access_token = auth_svc.issue_access_token(user, secrets.jwt_private_key)
    refresh_token, _ = auth_svc.issue_refresh_token(user, secrets.jwt_private_key)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/v1/auth/refresh",
    )
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, session: SessionDep) -> TokenResponse:
    secrets = get_secrets()
    user_repo = UserRepo(session)

    try:
        user = await auth_svc.login(
            email=str(body.email),
            password=body.password,
            user_repo=user_repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    access_token = auth_svc.issue_access_token(user, secrets.jwt_private_key)
    refresh_token, _ = auth_svc.issue_refresh_token(user, secrets.jwt_private_key)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/v1/auth/refresh",
    )
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    session: SessionDep,
    refresh_token: str | None = Cookie(default=None),
) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token cookie.",
        )
    secrets = get_secrets()
    user_repo = UserRepo(session)

    try:
        access_token, new_refresh, _ = await auth_svc.refresh(
            refresh_token=refresh_token,
            public_key=secrets.jwt_public_key,
            private_key=secrets.jwt_private_key,
            user_repo=user_repo,
        )
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/v1/auth/refresh",
    )
    return TokenResponse(access_token=access_token)


@router.get("/me")
async def me(current_user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    tenant_repo = TenantRepo(session)
    tenant = await tenant_repo.get_by_id(current_user.tenant_id)
    return {
        "user_id": current_user.user_id,
        "tenant_id": current_user.tenant_id,
        "email": current_user.email,
        "role": current_user.role,
        "operational_mode": tenant.mode if tenant else None,
    }


@router.get("/.well-known/jwks.json")
async def jwks() -> dict[str, Any]:
    """Expose the RSA public key as a JWK set for JWT verification by consumers."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from jwt.algorithms import RSAAlgorithm

    secrets = get_secrets()
    public_key = load_pem_public_key(secrets.jwt_public_key.encode())
    jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(public_key))  # type: ignore[arg-type]
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    jwk["kid"] = "mawrid-jwt-1"
    return {"keys": [jwk]}
