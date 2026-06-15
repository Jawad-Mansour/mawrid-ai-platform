"""
Feature:  AI Agents — Enrichment Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.enrichment_agent
Purpose:  Wraps the Phase 2 sequential enrichment pipeline in a LangGraph node.
          Pipeline: Icecat lookup → SearXNG web search → httpx+trafilatura scrape
          → GPT-4o spec extraction → GPT-4o description generation.
          Max 5 steps hard cap (enforced via step_count in state).
          Reads product_id from state task_description.
          Returns enrichment summary in specialist_result.
          Does NOT create HITL — enrichment is an internal catalog operation.
Depends:  langgraph, app.core.catalog.enrichment_pipeline, app.infra.db
HITL:     None — enrichment is internal.
"""

from __future__ import annotations

import logging
import re

from app.agents.supervisor import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

MAX_ENRICHMENT_STEPS = 5
_UUID_RE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", re.IGNORECASE
)
_HEX_RE = re.compile(r"\b([0-9a-f]{32})\b", re.IGNORECASE)


async def run(state: AgentState) -> AgentState:
    """
    Enrichment specialist node.
    Reads product_id from state, runs the enrichment pipeline.
    Enforces MAX_ENRICHMENT_STEPS limit.
    """
    step_count = state.get("step_count", 0)
    if step_count >= MAX_ENRICHMENT_STEPS:
        result = (
            f"Enrichment specialist: max steps ({MAX_ENRICHMENT_STEPS}) reached. "
            "Partial enrichment may have completed."
        )
        return {
            **state,
            "specialist_result": result,
            "messages": [*state["messages"], AIMessage(content=result)],
        }

    task = state.get("task_description", "")
    messages = state.get("messages", [])
    last_msg = str(messages[-1].content) if messages else task

    # Extract product_id from task description
    match = (
        _UUID_RE.search(task)
        or _UUID_RE.search(last_msg)
        or _HEX_RE.search(task)
        or _HEX_RE.search(last_msg)
    )
    product_id = match.group(1) if match else None

    if not product_id:
        result = (
            "Enrichment specialist: no product_id found. "
            "Provide a product_id (UUID or hex) to enrich."
        )
        return {
            **state,
            "specialist_result": result,
            "messages": [*state["messages"], AIMessage(content=result)],
        }

    try:
        from app.core.catalog.enrichment_pipeline import (  # noqa: PLC0415
            EnrichmentInput,
            build_pipeline,
        )
        from app.core.config import get_settings  # noqa: PLC0415
        from app.infra.db.repos.product_repo import ProductRepository  # noqa: PLC0415
        from app.infra.secrets.vault import get_secrets  # noqa: PLC0415
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

        settings = get_settings()
        secrets = get_secrets()
        engine = create_async_engine(str(settings.database_url), echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            product_repo = ProductRepository(session, state["tenant_id"])
            product = await product_repo.get_by_id(product_id)
            if product is None:
                result = f"Enrichment specialist: product {product_id!r} not found."
                await engine.dispose()
                return {
                    **state,
                    "specialist_result": result,
                    "messages": [*state["messages"], AIMessage(content=result)],
                }

            inp = EnrichmentInput(
                product_name=product.product_name,
                sku=product.sku,
                barcode=product.barcode,
                specifications={},
            )
            pipeline = build_pipeline(
                icecat_api_key=secrets.icecat_api_key,
                searxng_base_url=settings.searxng_base_url,
            )
            enriched = await pipeline.run(inp)
            result = (
                f"Enrichment complete for product '{enriched.product_name}' ({product_id}). "
                f"Source: {enriched.enrichment_source}. "
                f"Confidence: {enriched.enrichment_confidence}."
            )

        await engine.dispose()

    except Exception as exc:
        logger.warning("enrichment_specialist_failed", extra={"error": str(exc)})
        result = (
            f"Enrichment pipeline invoked for product {product_id} "
            f"(pipeline error: {exc!s}; retry via POST /catalog/products/{product_id}/enrich)"
        )

    return {
        **state,
        "specialist_result": result,
        "messages": [*state["messages"], AIMessage(content=result)],
    }
