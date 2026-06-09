"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Infra / DB Models
Module:   app.infra.db.models.hitl
Purpose:  SQLAlchemy ORM model for the `hitl_actions` table. JSONB payload
          stores action-specific data. Index on (tenant_id, status, action_type)
          for the live queue query. All 14 action_types and 6 statuses constrained
          via PostgreSQL CHECK constraints.
Depends:  app.infra.db.base, sqlalchemy
HITL:     This IS the HITL table.
"""

from typing import Any

from sqlalchemy import JSON, DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class HITLAction(TenantMixin, Base):
    __tablename__ = "hitl_actions"

    action_id: Mapped[str] = mapped_column(primary_key=True)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_hitl_queue", "tenant_id", "status", "action_type"),)
