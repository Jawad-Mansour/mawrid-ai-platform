"""
Feature:  NLP Search & RAG Pipeline
Layer:    API / Router
Module:   app.api.search
Purpose:  HTTP routes for semantic product search. /catalog/search uses
          enriched-scope retrieval (admin). /store/search uses published-scope
          (consumer). Both run the full RAG pipeline but return structured
          product results rather than a chat answer.
Depends:  app.rag.pipeline, app.infra.db.repos.product_repo, app.api.deps
HITL:     None — search is read-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.rag.pipeline import run_rag

router = APIRouter(prefix="/search", tags=["search"])


class ProductSearchResult(BaseModel):
    product_id: str
    chunk_text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[ProductSearchResult]
    answer: str | None = None


@router.get(
    "/catalog",
    response_model=SearchResponse,
    summary="Semantic catalog search — enriched products (admin scope)",
)
async def search_catalog(
    current_user: CurrentUser,
    session: SessionDep,
    q: str = Query(..., description="Search query"),
    include_answer: bool = False,
) -> SearchResponse:
    """
    Semantic search over enriched products. Returns ranked chunk results.
    Set include_answer=true to also generate an LLM summary answer.
    """
    result = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=q,
        scope="admin",
        top_k_retrieval=20,
        top_k_rerank=6,
    )
    return SearchResponse(
        query=q,
        results=[
            ProductSearchResult(
                product_id=c.product_id,
                chunk_text=c.chunk_text[:300],
                score=round(c.rerank_score, 4),
            )
            for c in result.source_chunks
        ],
        answer=result.answer if include_answer else None,
    )


@router.get(
    "/store",
    response_model=SearchResponse,
    summary="Semantic storefront search — published products (consumer scope)",
)
async def search_store(
    current_user: CurrentUser,
    session: SessionDep,
    q: str = Query(..., description="Search query"),
    include_answer: bool = False,
) -> SearchResponse:
    """
    Semantic search over published storefront products.
    """
    result = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=q,
        scope="consumer",
        top_k_retrieval=20,
        top_k_rerank=6,
    )
    return SearchResponse(
        query=q,
        results=[
            ProductSearchResult(
                product_id=c.product_id,
                chunk_text=c.chunk_text[:300],
                score=round(c.rerank_score, 4),
            )
            for c in result.source_chunks
        ],
        answer=result.answer if include_answer else None,
    )
