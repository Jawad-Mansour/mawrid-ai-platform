"""
Feature:  AI Chatbot (Admin + Consumer)
Layer:    API / Router
Module:   app.api.chat
Purpose:  HTTP routes for the importer-facing admin chatbot (enriched catalog
          scope) and the consumer-facing storefront chatbot (published scope).
          Phase 8 routing:
          1. 3-tier intent classifier runs on every admin message
          2. out_of_scope → immediate rejection (guardrails confirm)
          3. product_search → full 6-technique RAG pipeline
          4. direct_query intents (stock_check, order_status, shipment_status,
             invoice_query, dunning_action) → DB query handler (no LLM)
          5. complex_task → LangGraph Supervisor with async Redis checkpointing
          Consumer chatbot always uses RAG (published scope only, no direct DB).
          Both scopes: Phase 5 guardrails active (Presidio + NeMo).
Depends:  app.rag.pipeline, app.ml.intent.classifier, app.agents.supervisor,
          app.guardrails, app.api.deps
HITL:     Any write action initiated by the agent routes through hitl_actions.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.guardrails import get_default_guard
from app.rag.pipeline import RAGResult, run_rag

logger = logging.getLogger(__name__)

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
    intent: str | None = None
    route: str | None = None
    tier_used: int | None = None


@router.post(
    "/admin",
    response_model=ChatResponse,
    summary="Admin chatbot — 3-tier intent routing + RAG/Agent/Direct (importer-facing)",
)
async def chat_admin(
    body: ChatRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ChatResponse:
    """
    Full Phase 8 routing pipeline:
    1. Intent classification (3-tier)
    2. out_of_scope → reject
    3. product_search → RAG
    4. direct_query → DB handler
    5. complex_task → LangGraph Supervisor
    """
    from app.ml.intent.classifier import classify  # noqa: PLC0415

    session_id = body.session_id or uuid.uuid4().hex
    classification = await classify(body.query)

    # Reject off-topic before any LLM call
    if classification.route == "rejected":
        return ChatResponse(
            answer="I can only help with questions about your products, orders, suppliers, and operations.",
            sources=[],
            session_id=session_id,
            intent="out_of_scope",
            route="rejected",
            tier_used=classification.tier_used,
        )

    # Route: direct DB query (no LLM)
    if classification.route == "direct_query":
        answer = await _handle_direct_query(
            intent=classification.intent,
            query=body.query,
            tenant_id=current_user.tenant_id,
            session=session,
        )
        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
            intent=classification.intent,
            route="direct_query",
            tier_used=classification.tier_used,
        )

    # Route: LangGraph Supervisor for complex multi-step tasks
    if classification.route == "agent":
        answer = await _handle_agent_task(
            query=body.query,
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            session_id=session_id,
        )
        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
            intent=classification.intent,
            route="agent",
            tier_used=classification.tier_used,
        )

    # Default: RAG pipeline (product_search and fallback)
    result: RAGResult = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=body.query,
        scope="admin",
        guard=get_default_guard(),
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
        session_id=session_id,
        intent=classification.intent,
        route="rag",
        tier_used=classification.tier_used,
    )


@router.post(
    "/consumer",
    response_model=ChatResponse,
    summary="Consumer chatbot — published storefront scope (no direct DB, no agents)",
)
async def chat_consumer(
    body: ChatRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ChatResponse:
    """
    Consumer chatbot: always RAG over published products. No direct DB. No agents.
    Scope filter: storefront_status = 'published'.
    Consumer scope additionally blocks cost/margin/supplier data in output rail.
    """
    session_id = body.session_id or uuid.uuid4().hex

    result: RAGResult = await run_rag(
        session=session,
        tenant_id=current_user.tenant_id,
        query=body.query,
        scope="consumer",
        guard=get_default_guard(),
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
        session_id=session_id,
        intent="product_search",
        route="rag",
        tier_used=1,
    )


async def _handle_direct_query(
    intent: str,
    query: str,
    tenant_id: str,
    session: object,
) -> str:
    """Handle direct DB query intents without LLM. Returns human-readable answer."""
    try:

        from app.agents.mcp_servers.db_server import get_tool_functions  # noqa: PLC0415

        tools = get_tool_functions()

        if intent == "stock_check":
            # Extract product name from query (simple heuristic)
            results = await tools["check_stock"](query, tenant_id)
            if not results or (isinstance(results, list) and results and "error" in results[0]):
                return "No products matching your query were found in the catalog."
            lines = [f"- {r['name']}: {r.get('qty_in_stock', 0)} units in stock" for r in results if isinstance(r, dict)]
            return "Stock levels:\n" + "\n".join(lines) if lines else "No matching products found."

        if intent == "invoice_query":
            overdue = await tools["list_overdue_invoices"](tenant_id, 10)
            if not overdue or (isinstance(overdue, list) and overdue and "error" in overdue[0]):
                return "No overdue invoices found."
            lines = [
                f"- Invoice {r['invoice_id']}: {r.get('amount', 0)} (due {r.get('due_date', 'N/A')})"
                for r in overdue if isinstance(r, dict) and "invoice_id" in r
            ]
            return f"Overdue invoices ({len(lines)}):\n" + "\n".join(lines)

        if intent == "order_status":
            # Try to extract an order_id from the query
            import re  # noqa: PLC0415
            match = re.search(r"\b(PO[-\s]?\d{3,})\b", query, re.IGNORECASE)
            if match:
                order_id = match.group(1).replace(" ", "-")
                result = await tools["get_order_status"](order_id, tenant_id)
                if "error" not in result:
                    return f"Order {order_id}: status={result.get('status', 'unknown')}, supplier={result.get('supplier_id', 'N/A')}"
            return "Please provide a specific order ID (e.g., PO-2025-0042) to check its status."

        if intent == "shipment_status":
            import re  # noqa: PLC0415
            match = re.search(r"\b(PO[-\s]?\d{3,}|SHP[-\s]?\d{3,})\b", query, re.IGNORECASE)
            if match:
                ref = match.group(1).replace(" ", "-")
                result = await tools["get_shipment_status"](ref, tenant_id)
                if "error" not in result:
                    return f"Shipment for {ref}: status={result.get('status', 'unknown')}, ETA={result.get('eta', 'N/A')}"
            return "Please provide an order ID or shipment reference to track a shipment."

        if intent == "dunning_action":
            return (
                "To manage dunning sequences, use the HITL Approval Center or the dunning API endpoints. "
                "You can stop a sequence via POST /api/v1/dunning/sequences/{id}/stop or "
                "trigger manually via POST /api/v1/dunning/trigger/track{1,3,4}."
            )

    except Exception as exc:
        logger.warning("direct_query_failed", extra={"intent": intent, "error": str(exc)})
        return f"Unable to retrieve {intent.replace('_', ' ')} data right now. Please try the relevant API endpoint."

    return f"I received a {intent} query but couldn't find specific data. Please check the relevant section of the admin panel."


async def _handle_agent_task(
    query: str,
    tenant_id: str,
    user_id: str,
    session_id: str,
) -> str:
    """Route a complex_task to the LangGraph Supervisor."""
    try:
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        from app.agents.checkpointer import create_checkpointer, make_thread_id  # noqa: PLC0415
        from app.agents.supervisor import AgentState, run_agent  # noqa: PLC0415

        thread_id = make_thread_id(tenant_id, user_id, session_id)
        checkpointer = await create_checkpointer()

        initial_state = AgentState(
            messages=[HumanMessage(content=query)],
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            task_description=query,
            intent="complex_task",
            active_specialist=None,
            specialist_result=None,
            hitl_action_ids=[],
            bulk_pending=False,
            estimated_product_count=0,
            step_count=0,
            finished=False,
            error=None,
        )

        result_state = await run_agent(initial_state, checkpointer=checkpointer)
        answer = result_state.get("specialist_result") or "Task completed."
        hitl_ids = result_state.get("hitl_action_ids", [])
        if hitl_ids:
            answer += f"\n\n{len(hitl_ids)} HITL action(s) created — check the Approval Center."

        return answer

    except Exception as exc:
        logger.warning("agent_task_failed", extra={"error": str(exc)})
        return (
            f"The agent encountered an issue processing your request: {exc!s}. "
            "Please try rephrasing or use the relevant API endpoint."
        )
