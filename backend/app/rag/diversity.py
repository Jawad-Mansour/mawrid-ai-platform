"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG / Diversity
Module:   app.rag.diversity
Purpose:  Maximal Marginal Relevance (MMR) diversity pass. Applied after
          cross-encoder reranking to reduce redundant chunks before passing the
          context window to the LLM. Lambda (λ=0.5) balances relevance/diversity.
          MMR score: λ * sim(d_i, q) - (1-λ) * max_j(sim(d_i, d_j)) for selected j.
          Similarity is computed using rerank_score for relevance to query and
          cosine similarity between chunk texts (via TF-IDF bag-of-words).
Depends:  numpy, scikit-learn
HITL:     None.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag.retrieval import ChunkResult


def mmr_select(
    candidates: list[ChunkResult],
    top_k: int = 6,
    lambda_: float = 0.5,
) -> list[ChunkResult]:
    """
    Select top_k diverse chunks using MMR.
    If len(candidates) <= top_k, return all candidates unchanged.
    Uses normalized rerank_score as query relevance; TF-IDF cosine as chunk similarity.
    """
    if len(candidates) <= top_k:
        return candidates

    texts = [c.chunk_text for c in candidates]

    # Build TF-IDF similarity matrix between all candidate chunks
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
        chunk_sim: np.ndarray = cosine_similarity(tfidf_matrix)
    except ValueError:
        # TF-IDF fails on empty corpus — fall back to top-k by score
        return candidates[:top_k]

    # Normalize rerank scores to [0, 1]
    scores = np.array([c.rerank_score for c in candidates], dtype=float)
    score_range = scores.max() - scores.min()
    if score_range > 0:
        normalized_scores = (scores - scores.min()) / score_range
    else:
        normalized_scores = np.ones(len(candidates))

    selected_indices: list[int] = []
    remaining = list(range(len(candidates)))

    # Greedily select top_k chunks by MMR score
    for _ in range(top_k):
        if not remaining:
            break

        if not selected_indices:
            # First: pick the highest relevance chunk
            best = max(remaining, key=lambda i: normalized_scores[i])
        else:
            # Subsequent: pick chunk maximizing MMR
            best = max(
                remaining,
                key=lambda i: lambda_ * normalized_scores[i]
                - (1 - lambda_) * max(chunk_sim[i][j] for j in selected_indices),
            )

        selected_indices.append(best)
        remaining.remove(best)

    return [candidates[i] for i in selected_indices]
