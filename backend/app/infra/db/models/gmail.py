"""
Feature:  Connect Gmail — per-tenant OAuth mailbox connection
Layer:    Infra / DB Model
Module:   app.infra.db.models.gmail
Purpose:  ORM model for gmail_connections (one row per tenant) — the connected Gmail address
          and OAuth refresh token used to send-as-user and read replies.
Depends:  app.infra.db.base
HITL:     None — model only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class GmailConnection(Base):
    __tablename__ = "gmail_connections"

    tenant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
