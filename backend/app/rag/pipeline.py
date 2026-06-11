"""
Feature:  NLP Search & RAG Pipeline
Layer:    RAG
Module:   app.rag.pipeline
Purpose:  Orchestrates the full 6-technique RAG pipeline in runtime order:
          (1) HyDE + Multi-Query expansion → 5 query embeddings
          (2) Fan-out dense HNSW retrieval → RRF merge → top-20 child chunks
          (3) Parent-Doc mapping → swap child text for 1024-token parent context
          (4) GraphRAG 2-hop traversal → add related product context
          (5) Cross-Encoder reranking (ms-marco-MiniLM-L-6-v2) → top-6
          (6) MMR diversity (λ=0.5) → final context window
          → GPT-4o response → NeMo output guardrail (Phase 5 passthrough)
          Scope enforced at dense retrieval: admin=enriched, consumer=published.
Depends:  app.rag.expansion, app.rag.retrieval, app.rag.graph, app.rag.reranking,
          app.rag.diversity, app.infra.llm.openai
HITL:     None — RAG is read-only.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.llm.openai import chat_completion
from app.infra.vector.pgvector import Scope
from app.rag.diversity import mmr_select
from app.rag.expansion import expand_query
from app.rag.graph import graph_expand, load_graph
from app.rag.reranking import rerank
from app.rag.retrieval import ChunkResult, apply_parent_doc_mapping, dense_retrieve

logger = structlog.get_logger(__name__)


@dataclass
class RAGResult:
    answer: str
    source_chunks: list[ChunkResult]
    query: str
    scope: str


async def run_rag(
    session: AsyncSession,
    tenant_id: str,
    query: str,
    scope: Scope = "admin",
    top_k_retrieval: int = 20,
    top_k_rerank: int = 6,
) -> RAGResult:
    """
    Full 6-technique RAG pipeline. Gracefully degrades at each step:
    empty candidates at any step return an LLM response with no context.
    """
    logger.info("rag_start", query=query, scope=scope, tenant_id=tenant_id)

    # Step 1: HyDE + Multi-Query expansion
    expanded = await expand_query(query)
    logger.debug("rag_expansion_done", n_embeddings=len(expanded.embeddings))

    # Step 2+3: Dense retrieval with RRF merge across all query variants
    candidates = await dense_retrieve(
        session=session,
        tenant_id=tenant_id,
        query_embeddings=expanded.embeddings,
        top_k=top_k_retrieval,
        scope=scope,
    )
    logger.debug("rag_dense_done", n_candidates=len(candidates))

    # Step 4: Parent-Doc mapping (swap child chunks for richer parent context)
    candidates = await apply_parent_doc_mapping(session, tenant_id, candidates)
    logger.debug("rag_parent_doc_done", n_candidates=len(candidates))

    # Step 5: GraphRAG — add 2-hop related products
    if candidates:  # only worth loading graph if we have seed products
        graph = await load_graph(session, tenant_id)
        candidates = await graph_expand(
            session=session,
            tenant_id=tenant_id,
            candidates=candidates,
            graph=graph,
        )
        logger.debug("rag_graph_done", n_candidates=len(candidates))

    # Step 6: Cross-Encoder reranking top-20 → top-6
    reranked = await rerank(query=query, candidates=candidates, top_k=top_k_rerank)
    logger.debug("rag_rerank_done", n_reranked=len(reranked))

    # Step 7: MMR diversity pass
    final_chunks = mmr_select(reranked, top_k=top_k_rerank)
    logger.debug("rag_mmr_done", n_final=len(final_chunks))

    # Step 8: Build context and call GPT-4o
    answer = await _generate_answer(query=query, chunks=final_chunks, scope=scope)

    # Step 9: NeMo output guardrail — Phase 5 passthrough
    # TODO Phase 5: wrap answer through NeMo output rail

    logger.info("rag_complete", n_sources=len(final_chunks))
    return RAGResult(
        answer=answer,
        source_chunks=final_chunks,
        query=query,
        scope=scope,
    )


async def _generate_answer(
    query: str,
    chunks: list[ChunkResult],
    scope: str,
) -> str:
    """Build context window from chunks and call GPT-4o for the final answer."""
    if not chunks:
        return (
            "I couldn't find relevant products for your query. "
            "Try rephrasing or broadening your search."
        )

    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        context_parts.append(f"[{i}] Product ID: {chunk.product_id}\n{chunk.chunk_text}")
    context = "\n\n---\n\n".join(context_parts)

    scope_instruction = (
        "You are assisting an importer with their internal product catalog."
        if scope == "admin"
        else "You are assisting a customer browsing published products."
    )

    system = (
        f"{scope_instruction} "
        "Answer using ONLY the provided product context. "
        "If the context doesn't contain the answer, say so. "
        "Be concise and accurate."
    )
    user = f"""Product context:
{context}

---

Question: {query}"""

    return await chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=1024,
    )
