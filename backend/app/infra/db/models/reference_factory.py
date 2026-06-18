"""
Feature:  Supplier & Factory Network
Layer:    Infra / DB Models
Module:   app.infra.db.models.reference_factory
Purpose:  Global (NOT tenant-scoped) reference dataset of REAL, verifiable
          manufacturers / factories with real coordinates, websites and what they
          make. Seeded from scripts/seed_factories.py. Read-only reference layer
          that powers the Network map alongside each tenant's own saved/discovered
          suppliers. No mock data — every row is a real, publicly documented company.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""

from sqlalchemy import Float, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class ReferenceFactory(Base):
    __tablename__ = "reference_factories"

    factory_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    subcategory: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    offering: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition: Mapped[str] = mapped_column(Text, nullable=False, server_default="new")
    region: Mapped[str] = mapped_column(Text, nullable=False, server_default="europe")
    email: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_reference_factories_region_cat", "region", "category"),)
