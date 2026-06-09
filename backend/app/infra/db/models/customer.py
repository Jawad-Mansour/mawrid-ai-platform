"""
Feature:  Customer Management
Layer:    Infra / DB Models
Module:   app.infra.db.models.customer
Purpose:  SQLAlchemy ORM model for customers table. Unique constraints on
          (tenant_id, email) and (tenant_id, phone) for exact-match lookups
          in customer matching waterfall. payment_history_score used by
          dunning tone classifier.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from sqlalchemy import Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class Customer(TenantMixin, Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(primary_key=True)
    customer_type: Mapped[str] = mapped_column(Text, nullable=False)  # b2b | b2c
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_history_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_customer_email_per_tenant"),
        UniqueConstraint("tenant_id", "phone", name="uq_customer_phone_per_tenant"),
    )
