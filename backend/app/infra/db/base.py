"""
Feature:  Database (cross-cutting)
Layer:    Infra / DB
Module:   app.infra.db.base
Purpose:  SQLAlchemy declarative base and TenantMixin. TenantMixin adds
          tenant_id column with not-null constraint. All tables that hold
          tenant data inherit this mixin. Alembic imports Base to discover all
          table models.
Depends:  sqlalchemy
HITL:     None — infrastructure only.
"""

from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Mixin that adds tenant_id to any table. Used with PostgreSQL RLS."""

    tenant_id: MappedColumn[str] = mapped_column(nullable=False, index=True)
