"""
Feature:  Activity & Notifications (cross-cutting)
Layer:    Infra / DB Models
Module:   app.infra.db.models.notification
Purpose:  SQLAlchemy ORM model for the `notifications` table — a per-tenant event
          log written as real events happen (enrichment done, order created, PO
          sent, supplier reply, outreach sent…). Powers the Activity page and the
          unread badge. Distinct from the derived "needs attention" Notifications
          view, which is computed live from current state.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Notification(TenantMixin, Base):
    __tablename__ = "notifications"

    notification_id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (Index("ix_notifications_tenant_created", "tenant_id", "created_at"),)
