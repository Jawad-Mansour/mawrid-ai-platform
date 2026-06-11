"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Query Expansion
Module:   app.rag.expansion
Purpose:  Query expansion step (step 1 of the RAG pipeline).
          HyDE: generates a hypothetical answer document via GPT-4o-mini, embeds
          it, uses that embedding for dense retrieval.
          Multi-Query: generates 3 alternative phrasings of the user query via
          GPT-4o-mini; all variants + original searched separately.
          Both result sets merged via Reciprocal Rank Fusion (RRF k=60).
Depends:  app.infra.llm.openai, app.infra.vector.embedder
HITL:     None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from app.infra.llm.openai import chat_completion
from app.infra.vector.embedder import embed_many

T = TypeVar("T")

_RRF_K = 60  # standard constant for reciprocal rank fusion


@dataclass
class ExpandedQuery:
    original: str
    hyde_text: str
    multi_queries: list[str]
    embeddings: list[list[float]]  # [original, hyde, mq1, mq2, mq3]


async def expand_query(query: str) -> ExpandedQuery:
    """
    Generate HyDE document + 3 Multi-Query variants and embed all of them.
    Returns an ExpandedQuery with 5 embeddings for fan-out dense retrieval.
    """
    hyde_text, multi_queries = await _generate_expansions(query)

    all_texts = [query, hyde_text] + multi_queries
    all_embeddings = await embed_many(all_texts)

    return ExpandedQuery(
        original=query,
        hyde_text=hyde_text,
        multi_queries=multi_queries,
        embeddings=all_embeddings,
    )


async def _generate_expansions(query: str) -> tuple[str, list[str]]:
    """Call GPT-4o-mini once for HyDE + Multi-Query expansion (single prompt)."""
    system = (
        "You are a search assistant for a product catalog. "
        "Respond strictly in the JSON format requested."
    )
    user = f"""Given this product search query: "{query}"

Return a JSON object with two fields:
1. "hypothetical_document": A 2-3 sentence product description that would perfectly answer this query.
2. "multi_queries": A list of exactly 3 alternative phrasings of the same query.

JSON only, no markdown fences."""

    raw = await chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=512,
    )

    try:
        import json

        data = json.loads(raw)
        hyde_text = str(data.get("hypothetical_document", query))
        variants = data.get("multi_queries", [])
        multi_queries = [str(v) for v in variants[:3]]
        while len(multi_queries) < 3:
            multi_queries.append(query)
    except Exception:
        # Graceful degrade — fall back to original query repeated
        hyde_text = query
        multi_queries = [query, query, query]

    return hyde_text, multi_queries


def rrf_merge(ranked_lists: list[list[T]], k: int = _RRF_K) -> list[tuple[T, float]]:
    """
    Reciprocal Rank Fusion across multiple ranked result lists.
    Returns list of (item, rrf_score) sorted by descending score.
    Items are compared by identity (id()), so use the same object across lists.
    """
    scores: dict[int, tuple[T, float]] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            item_id = id(item)
            rrf_score = 1.0 / (k + rank)
            if item_id in scores:
                _, existing = scores[item_id]
                scores[item_id] = (item, existing + rrf_score)
            else:
                scores[item_id] = (item, rrf_score)

    return sorted(scores.values(), key=lambda x: x[1], reverse=True)
