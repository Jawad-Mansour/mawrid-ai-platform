"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Retrieval
Module:   app.rag.retrieval
Purpose:  Dense retrieval using pgvector HNSW index (top-20 candidates per query).
          Parent-Doc chunk mapping: child chunks retrieved by embedding, then their
          parent text (1024-token context) replaces the child (256-token) for the
          LLM context window. Always applies tenant_id filter.
          Step 3 of the RAG runtime pipeline (after RRF merge).
Depends:  app.infra.vector.pgvector
HITL:     None.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.vector.pgvector import Scope, VectorHit, fetch_parent_chunks, search_chunks


@dataclass
class ChunkResult:
    chunk_id: str
    product_id: str
    chunk_type: str
    parent_chunk_id: str | None
    chunk_text: str  # May be upgraded to parent text by parent-doc mapping
    rrf_score: float = 0.0
    rerank_score: float = field(default=0.0)


async def dense_retrieve(
    session: AsyncSession,
    tenant_id: str,
    query_embeddings: list[list[float]],
    top_k: int = 20,
    scope: Scope = "admin",
) -> list[ChunkResult]:
    """
    Fan-out dense retrieval: one HNSW search per query embedding.
    Deduplicates by chunk_id, keeps the best score across all query variants.
    Returns up to top_k unique child chunks.
    """
    seen: dict[str, ChunkResult] = {}

    for embedding in query_embeddings:
        hits = await search_chunks(
            session=session,
            tenant_id=tenant_id,
            query_embedding=embedding,
            top_k=top_k,
            scope=scope,
            chunk_type="child",
        )
        for rank, hit in enumerate(hits, start=1):
            rrf_score = 1.0 / (60 + rank)
            if hit.chunk_id not in seen:
                seen[hit.chunk_id] = ChunkResult(
                    chunk_id=hit.chunk_id,
                    product_id=hit.product_id,
                    chunk_type=hit.chunk_type,
                    parent_chunk_id=hit.parent_chunk_id,
                    chunk_text=hit.chunk_text,
                    rrf_score=rrf_score,
                )
            else:
                # Accumulate RRF scores across query variants
                seen[hit.chunk_id].rrf_score += rrf_score

    candidates = sorted(seen.values(), key=lambda c: c.rrf_score, reverse=True)
    return candidates[:top_k]


async def apply_parent_doc_mapping(
    session: AsyncSession,
    tenant_id: str,
    chunks: list[ChunkResult],
) -> list[ChunkResult]:
    """
    Replace child chunk text with their parent chunk text (1024-token context).
    Child chunks with no parent_chunk_id are left unchanged.
    Deduplicates: multiple children of the same parent become one parent entry.
    """
    parent_ids = [c.parent_chunk_id for c in chunks if c.parent_chunk_id]
    if not parent_ids:
        return chunks

    parent_map: dict[str, VectorHit] = await fetch_parent_chunks(session, tenant_id, parent_ids)

    seen_parents: set[str] = set()
    upgraded: list[ChunkResult] = []

    for chunk in chunks:
        if chunk.parent_chunk_id and chunk.parent_chunk_id in parent_map:
            pid = chunk.parent_chunk_id
            if pid in seen_parents:
                continue  # already added this parent
            seen_parents.add(pid)
            parent = parent_map[pid]
            upgraded.append(
                ChunkResult(
                    chunk_id=parent.chunk_id,
                    product_id=parent.product_id,
                    chunk_type="parent",
                    parent_chunk_id=None,
                    chunk_text=parent.chunk_text,
                    rrf_score=chunk.rrf_score,
                )
            )
        else:
            upgraded.append(chunk)

    return upgraded
