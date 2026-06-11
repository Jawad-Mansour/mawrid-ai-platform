"""
Feature:  RAG Pipeline — Parent-Doc Chunk Mapping
Layer:    Infra / DB Models
Module:   app.infra.db.models.product_chunks
Purpose:  SQLAlchemy ORM for `product_chunks` table. Stores parent (1024 tokens)
          and child (256 tokens) chunks of product text with separate 1536-dim
          embeddings. Child chunks are used for HNSW dense retrieval; the parent
          text is what gets passed to the LLM context window.
Depends:  app.infra.db.base, pgvector
HITL:     None — model only.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, TenantMixin


class ProductChunk(TenantMixin, Base):
    __tablename__ = "product_chunks"

    chunk_id: Mapped[str] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)  # "parent" | "child"
    parent_chunk_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # child → parent
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )
