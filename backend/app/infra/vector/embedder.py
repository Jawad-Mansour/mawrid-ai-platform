"""
Feature:  Catalog Enrichment / RAG Pipeline (cross-cutting)
Layer:    Infra / Vector
Module:   app.infra.vector.embedder
Purpose:  Async embedding client using text-embedding-3-small (1536-dim via
          OpenAI API). Used by the outbox relay (product embeddings) and the
          RAG pipeline (query embeddings for HyDE + dense retrieval).
          Single string and batch variants both available.
Depends:  app.infra.llm.openai
HITL:     None.
"""

from __future__ import annotations

from app.infra.llm.openai import embed_batch, embed_text


async def embed(text: str) -> list[float]:
    """Embed a single text. Returns 1536-dim vector."""
    return await embed_text(text)


async def embed_many(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts in one API call. Returns list of 1536-dim vectors."""
    return await embed_batch(texts)
