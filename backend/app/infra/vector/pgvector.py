"""
Feature:  RAG Pipeline / Catalog Enrichment (cross-cutting)
Layer:    Infra / Vector
Module:   app.infra.vector.pgvector
Purpose:  pgvector HNSW search client. ALL searches include a mandatory tenant_id
          filter — this is the third tenant isolation layer. Scope filters:
          admin chatbot: WHERE p.enrichment_status='enriched'
          consumer chatbot: WHERE p.storefront_status='published'
          Returns top-K child chunk candidates for cross-encoder reranking.
Depends:  sqlalchemy, pgvector
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Scope = Literal["admin", "consumer", "all"]


@dataclass
class VectorHit:
    chunk_id: str
    product_id: str
    chunk_type: str
    parent_chunk_id: str | None
    chunk_text: str
    embedding: list[float]
    distance: float
    score: float = field(init=False)

    def __post_init__(self) -> None:
        # Convert cosine distance (0=identical, 2=opposite) → score in [0, 1]
        self.score = max(0.0, 1.0 - self.distance)


async def search_chunks(
    session: AsyncSession,
    tenant_id: str,
    query_embedding: list[float],
    top_k: int = 20,
    scope: Scope = "admin",
    chunk_type: str = "child",
) -> list[VectorHit]:
    """
    Cosine-distance HNSW search over product_chunks. Always filters by
    tenant_id (layer 3 isolation). Applies scope filter via join to products.
    """
    scope_filter = _scope_filter(scope)

    # Build the chunk_type filter conditionally. A bare ":param IS NULL" makes
    # asyncpg unable to infer the parameter's type (AmbiguousParameterError), so
    # we only add the clause when a concrete chunk_type is requested.
    params: dict[str, object] = {
        "tenant_id": tenant_id,
        "query_vec": "[" + ",".join(str(v) for v in query_embedding) + "]",
        "top_k": top_k,
    }
    chunk_type_filter = ""
    if chunk_type and chunk_type != "any":
        chunk_type_filter = "AND pc.chunk_type = :chunk_type"
        params["chunk_type"] = chunk_type

    # pgvector cosine distance operator: <=>
    sql = text(
        f"""
        SELECT
            pc.chunk_id,
            pc.product_id,
            pc.chunk_type,
            pc.parent_chunk_id,
            pc.chunk_text,
            pc.embedding::text AS embedding_text,
            pc.embedding <=> CAST(:query_vec AS vector) AS distance
        FROM product_chunks pc
        JOIN products p ON pc.product_id = p.product_id
        WHERE pc.tenant_id = :tenant_id
          AND p.tenant_id = :tenant_id
          {chunk_type_filter}
          {scope_filter}
        ORDER BY pc.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
        """
    )
    result = await session.execute(sql, params)
    rows = result.fetchall()
    return [
        VectorHit(
            chunk_id=row.chunk_id,
            product_id=row.product_id,
            chunk_type=row.chunk_type,
            parent_chunk_id=row.parent_chunk_id,
            chunk_text=row.chunk_text,
            embedding=[],  # skip deserializing — not needed after retrieval
            distance=float(row.distance),
        )
        for row in rows
    ]


async def fetch_parent_chunks(
    session: AsyncSession,
    tenant_id: str,
    parent_chunk_ids: list[str],
) -> dict[str, VectorHit]:
    """Fetch parent chunks by ID list. Used for Parent-Doc mapping."""
    if not parent_chunk_ids:
        return {}
    sql = text(
        """
        SELECT chunk_id, product_id, chunk_type, parent_chunk_id, chunk_text
        FROM product_chunks
        WHERE tenant_id = :tenant_id
          AND chunk_id = ANY(:ids)
        """
    )
    result = await session.execute(sql, {"tenant_id": tenant_id, "ids": parent_chunk_ids})
    rows = result.fetchall()
    return {
        row.chunk_id: VectorHit(
            chunk_id=row.chunk_id,
            product_id=row.product_id,
            chunk_type=row.chunk_type,
            parent_chunk_id=row.parent_chunk_id,
            chunk_text=row.chunk_text,
            embedding=[],
            distance=0.0,
        )
        for row in rows
    }


def _scope_filter(scope: Scope) -> str:
    if scope == "admin":
        return "AND p.enrichment_status = 'enriched'"
    if scope == "consumer":
        return "AND p.storefront_status = 'published'"
    return ""  # "all" — no extra filter
