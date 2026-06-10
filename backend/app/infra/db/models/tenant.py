"""
Feature:  Authentication & Tenant Onboarding
Layer:    Infra / DB Models
Module:   app.infra.db.models.tenant
Purpose:  SQLAlchemy ORM models for the `tenants` and `users` tables.
          Tenants is the root table — it has no tenant_id column itself
          (it IS the tenant). Users belong to a tenant. Role enum:
          admin | staff | viewer. Mode enum: hybrid | wholesale_only | retail_only.
          Passwords stored as argon2id hashes. RS256 JWT issued on login.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="hybrid")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(TenantMixin, Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)
