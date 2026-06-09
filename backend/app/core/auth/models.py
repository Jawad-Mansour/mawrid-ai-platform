"""
Feature:  Authentication & Tenant Onboarding
Layer:    Core / Domain Models
Module:   app.core.auth.models
Purpose:  Pydantic v2 domain models for Tenant, User, JWT claims, and
          operational mode enum. These are pure Python objects — no DB imports.
Depends:  pydantic
HITL:     None.
"""

from enum import StrEnum

from pydantic import BaseModel, EmailStr


class OperationalMode(StrEnum):
    HYBRID = "hybrid"
    WHOLESALE_ONLY = "wholesale_only"
    RETAIL_ONLY = "retail_only"


class TenantDomain(BaseModel):
    model_config = {"extra": "forbid"}

    tenant_id: str
    name: str
    mode: OperationalMode


class UserDomain(BaseModel):
    model_config = {"extra": "forbid"}

    user_id: str
    tenant_id: str
    email: EmailStr
    role: str


class JWTClaims(BaseModel):
    model_config = {"extra": "forbid"}

    sub: str
    tenant_id: str
    role: str
    exp: int
