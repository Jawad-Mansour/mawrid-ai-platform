"""
Feature:  NLP Search & RAG Pipeline — Parent/Child Chunking
Layer:    RAG
Module:   app.rag.chunker
Purpose:  Split a product's enriched text into parent (≈1024-token) and child
          (≈256-token, 32-token overlap) chunks for the Parent-Doc retrieval
          strategy. Child chunks are embedded and indexed for HNSW dense
          retrieval; the parent text is what reaches the LLM context window.
          Token counts are approximated by whitespace words (deterministic, no
          network/model download) — sufficient for retrieval-grade chunking.
Depends:  (stdlib only)
HITL:     None — pure function.
"""

from __future__ import annotations

from dataclasses import dataclass

# Window sizes expressed in approximate tokens (1 token ≈ 1 whitespace word here).
PARENT_TOKENS = 1024
CHILD_TOKENS = 256
CHILD_OVERLAP = 32


@dataclass(frozen=True)
class ChunkSpec:
    """A single chunk to be embedded and stored. parent_index links a child to
    the parent chunk that contains its starting word."""

    chunk_type: str  # "parent" | "child"
    chunk_index: int
    chunk_text: str
    parent_index: int | None = None


def _windows(words: list[str], size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) word-index spans for a sliding window."""
    if size <= 0:
        return []
    spans: list[tuple[int, int]] = []
    step = max(1, size - overlap)
    start = 0
    n = len(words)
    while start < n:
        end = min(start + size, n)
        spans.append((start, end))
        if end >= n:
            break
        start += step
    return spans


def build_chunks(
    text: str,
    parent_tokens: int = PARENT_TOKENS,
    child_tokens: int = CHILD_TOKENS,
    child_overlap: int = CHILD_OVERLAP,
) -> list[ChunkSpec]:
    """
    Build parent and child chunks from product text.

    - Parents: contiguous, non-overlapping windows of ~parent_tokens words.
    - Children: ~child_tokens windows with child_overlap, each assigned to the
      parent whose word-span contains the child's start index.
    Empty/whitespace text yields no chunks.
    """
    words = text.split()
    if not words:
        return []

    specs: list[ChunkSpec] = []

    # Parent windows (no overlap).
    parent_spans = _windows(words, parent_tokens, 0)
    for p_idx, (p_start, p_end) in enumerate(parent_spans):
        specs.append(
            ChunkSpec(
                chunk_type="parent",
                chunk_index=p_idx,
                chunk_text=" ".join(words[p_start:p_end]),
            )
        )

    def _parent_index_for(start: int) -> int:
        for p_idx, (p_start, p_end) in enumerate(parent_spans):
            if p_start <= start < p_end:
                return p_idx
        return len(parent_spans) - 1  # fall back to last parent

    # Child windows (overlapping), linked to their containing parent.
    child_spans = _windows(words, child_tokens, child_overlap)
    for c_idx, (c_start, c_end) in enumerate(child_spans):
        specs.append(
            ChunkSpec(
                chunk_type="child",
                chunk_index=c_idx,
                chunk_text=" ".join(words[c_start:c_end]),
                parent_index=_parent_index_for(c_start),
            )
        )

    return specs
