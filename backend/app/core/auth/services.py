"""
Feature:  Authentication & Tenant Onboarding
Layer:    Core / Service
Module:   app.core.auth.services
Purpose:  Business logic for signup (tenant provisioning), login (argon2id
          password verification, RS256 JWT issuance), and token refresh.
          JWT private/public keys come from VaultSecrets (injected at call site).
Depends:  app.core.auth.models, app.infra.db.repos.tenant_repo, argon2-cffi, pyjwt
HITL:     None.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.auth.models import JWTClaims, OperationalMode, TenantDomain, UserDomain
from app.infra.db.repos.tenant_repo import TenantRepo, UserRepo

_ph = PasswordHasher()

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)
JWT_ALGORITHM = "RS256"


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def _issue_token(
    payload: dict[str, Any],
    private_key: str,
    ttl: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm=JWT_ALGORITHM)


def issue_access_token(user: UserDomain, private_key: str) -> str:
    return _issue_token(
        {
            "sub": user.user_id,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "type": "access",
        },
        private_key,
        ACCESS_TOKEN_TTL,
    )


def issue_refresh_token(user: UserDomain, private_key: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    token = _issue_token(
        {
            "sub": user.user_id,
            "tenant_id": user.tenant_id,
            "jti": jti,
            "type": "refresh",
        },
        private_key,
        REFRESH_TOKEN_TTL,
    )
    return token, jti


def decode_token(token: str, public_key: str) -> JWTClaims:
    raw = jwt.decode(token, public_key, algorithms=[JWT_ALGORITHM])
    return JWTClaims(
        sub=str(raw["sub"]),
        tenant_id=str(raw["tenant_id"]),
        role=str(raw["role"]),
        exp=int(raw["exp"]),
    )


async def signup(
    company_name: str,
    email: str,
    password: str,
    mode: str,
    tenant_repo: TenantRepo,
    user_repo: UserRepo,
) -> tuple[TenantDomain, UserDomain]:
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    tenant_orm = await tenant_repo.create(tenant_id=tenant_id, name=company_name, mode=mode)
    user_orm = await user_repo.create(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        password_hash=password_hash,
        role="admin",
    )

    tenant_domain = TenantDomain(
        tenant_id=tenant_orm.tenant_id,
        name=tenant_orm.name,
        mode=OperationalMode(tenant_orm.mode),
    )
    user_domain = UserDomain(
        user_id=user_orm.user_id,
        tenant_id=user_orm.tenant_id,
        email=user_orm.email,
        role=user_orm.role,
    )
    return tenant_domain, user_domain


async def login(
    email: str,
    password: str,
    user_repo: UserRepo,
) -> UserDomain:
    user_orm = await user_repo.get_by_email(email)
    if user_orm is None or not verify_password(user_orm.password_hash, password):
        raise ValueError("Invalid email or password.")
    if not user_orm.is_active:
        raise ValueError("Account is deactivated.")
    return UserDomain(
        user_id=user_orm.user_id,
        tenant_id=user_orm.tenant_id,
        email=user_orm.email,
        role=user_orm.role,
    )


async def refresh(
    refresh_token: str,
    public_key: str,
    private_key: str,
    user_repo: UserRepo,
) -> tuple[str, str, str]:
    """Verify refresh token, return new access_token, refresh_token, and new jti."""
    raw = jwt.decode(refresh_token, public_key, algorithms=[JWT_ALGORITHM])
    if raw.get("type") != "refresh":
        raise ValueError("Token is not a refresh token.")

    user_orm = await user_repo.get_by_id(str(raw["sub"]))
    if user_orm is None or not user_orm.is_active:
        raise ValueError("User not found or deactivated.")

    user_domain = UserDomain(
        user_id=user_orm.user_id,
        tenant_id=user_orm.tenant_id,
        email=user_orm.email,
        role=user_orm.role,
    )
    access_token = issue_access_token(user_domain, private_key)
    new_refresh_token, new_jti = issue_refresh_token(user_domain, private_key)
    return access_token, new_refresh_token, new_jti
