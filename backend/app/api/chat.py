"""
Feature:  AI Chatbot (Admin + Consumer)
Layer:    API / Router
Module:   app.api.chat
Purpose:  HTTP routes for the importer-facing admin chatbot (enriched catalog
          scope) and the consumer-facing storefront chatbot (published scope).
          Both use the full 6-technique RAG pipeline. Scope enforced at the
          dense retrieval step. Phase 8 adds the 3-tier intent classifier and
          LangGraph supervisor — this endpoint calls the RAG pipeline directly.
Depends:  app.rag.pipeline, app.api.deps
HITL:     Any write action initiated by the agent routes through hitl_actions.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.rag.pipeline import RAGResult, run_rag

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class ChunkSource(BaseModel):
    chunk_id: str
    product_id: str
    chunk_text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChunkSource]
    session_id: str | None


@router.post(
    "/admin",
    response_model=ChatResponse,
    summary="Admin chatbot — enriched catalog scope (importer-facing)",
)
async def chat_admin(
    body: ChatRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ChatResponse:
    """
    Full 6-technique RAG over enriched products.
    Scope filter: enrichment_status = 'enriched'.
    Phase 8 wraps this with the 3-tier intent classifier + LangGraph supervisor.
    """
    result: RAGResult = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=body.query,
        scope="admin",
    )
    return ChatResponse(
        answer=result.answer,
        sources=[
            ChunkSource(
                chunk_id=c.chunk_id,
                product_id=c.product_id,
                chunk_text=c.chunk_text[:500],  # truncate for response payload
                score=round(c.rerank_score, 4),
            )
            for c in result.source_chunks
        ],
        session_id=body.session_id,
    )


@router.post(
    "/consumer",
    response_model=ChatResponse,
    summary="Consumer chatbot — published storefront scope",
)
async def chat_consumer(
    body: ChatRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ChatResponse:
    """
    Full 6-technique RAG over published products only.
    Scope filter: storefront_status = 'published'.
    """
    result: RAGResult = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=body.query,
        scope="consumer",
    )
    return ChatResponse(
        answer=result.answer,
        sources=[
            ChunkSource(
                chunk_id=c.chunk_id,
                product_id=c.product_id,
                chunk_text=c.chunk_text[:500],
                score=round(c.rerank_score, 4),
            )
            for c in result.source_chunks
        ],
        session_id=body.session_id,
    )
