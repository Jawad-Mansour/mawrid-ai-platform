"""
Feature:  NLP Search & RAG Pipeline (GraphRAG)
Layer:    Infra / DB Models
Module:   app.infra.db.models.graph
Purpose:  SQLAlchemy ORM model for `graph_edges` table. Stores the knowledge
          graph edges used by the GraphRAG pipeline: product→supplier,
          product→category, supplier→category relationships. Edge weights
          reflect co-occurrence frequency. Tenant-scoped. Loaded into networkx
          at query time for graph traversal during RAG retrieval.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None.
"""

from datetime import datetime

from sqlalchemy import DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class GraphEdge(TenantMixin, Base):
    __tablename__ = "graph_edges"

    edge_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(6, 4), default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
