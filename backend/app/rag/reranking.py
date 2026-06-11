"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Reranking
Module:   app.rag.reranking
Purpose:  Cross-Encoder reranking using ms-marco-MiniLM-L-6-v2 (CPU).
          Model loaded lazily on first call — not downloaded at runtime (must be
          cached locally by sentence-transformers or pre-downloaded in Docker image).
          Takes top-20 candidates from retrieval+GraphRAG pool, scores each
          (query, chunk_text) pair with the cross-encoder, returns top-6.
Depends:  sentence-transformers (CrossEncoder), app.rag.retrieval
HITL:     None.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from app.rag.retrieval import ChunkResult

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = structlog.get_logger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_cross_encoder: CrossEncoder | None = None


def _get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415

        logger.info("loading_cross_encoder", model=_MODEL_NAME)
        _cross_encoder = CrossEncoder(_MODEL_NAME, max_length=512)
        logger.info("cross_encoder_loaded")
    return _cross_encoder


def _rerank_sync(
    query: str,
    candidates: list[ChunkResult],
    top_k: int,
) -> list[ChunkResult]:
    """Run cross-encoder scoring synchronously (CPU-bound, called via to_thread)."""
    ce = _get_cross_encoder()
    pairs = [(query, c.chunk_text) for c in candidates]
    scores: list[float] = ce.predict(pairs, show_progress_bar=False).tolist()  # type: ignore[arg-type]

    for chunk, score in zip(candidates, scores, strict=False):
        chunk.rerank_score = float(score)

    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]


async def rerank(
    query: str,
    candidates: list[ChunkResult],
    top_k: int = 6,
) -> list[ChunkResult]:
    """
    Async wrapper for cross-encoder reranking.
    Runs the CPU-bound model in a thread pool to avoid blocking the event loop.
    """
    if not candidates:
        return []

    return await asyncio.get_event_loop().run_in_executor(
        None,
        _rerank_sync,
        query,
        candidates,
        top_k,
    )
