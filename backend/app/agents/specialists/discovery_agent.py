"""
Feature:  AI Agents — Discovery Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.discovery_agent
Purpose:  Discovers new suppliers for a product category via SearXNG web search.
          Wraps the Phase 7 discover_suppliers() service:
          1. Parses product_name and category from task_description
          2. SearXNG search → top 3 candidates
          3. GPT-4o drafts outreach email per candidate
          4. Creates supplier_outreach HITL action per candidate
          Returns count and action IDs in specialist_result.
          No email is sent without importer approval.
Depends:  langgraph, app.core.suppliers.services, app.infra.db
HITL:     supplier_outreach (one per discovered candidate, max 3)
"""

from __future__ import annotations

import logging
import re

from app.agents.supervisor import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS = [
    "appliance", "electronics", "food", "beverage", "cleaning", "dairy",
    "personal care", "frozen", "clothing", "pharmaceutical",
]


def _parse_discovery_params(task: str) -> tuple[str, str]:
    """Extract (product_name, category) from a free-text task description."""
    task_lower = task.lower()
    category = next((kw for kw in _CATEGORY_KEYWORDS if kw in task_lower), "general")

    # Use the full task as product_name if we can't parse a specific product
    # Remove common filler words
    product_name = re.sub(r"\b(find|search|discover|new|supplier|for|a|an|the)\b", "", task_lower).strip()
    product_name = product_name[:80] or task[:80]  # cap length

    return product_name, category


async def run(state: AgentState) -> AgentState:
    """
    Discovery specialist node.
    Parses product/category from task, runs supplier discovery,
    creates HITL outreach actions.
    """
    task = state.get("task_description", "")
    messages_list = state.get("messages", [])
    last_msg = str(messages_list[-1].content) if messages_list else task

    product_name, category = _parse_discovery_params(task or last_msg)

    try:
        from app.core.config import get_settings  # noqa: PLC0415
        from app.core.suppliers.services import discover_suppliers  # noqa: PLC0415
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

        settings = get_settings()
        engine = create_async_engine(str(settings.database_url), echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            action_ids = await discover_suppliers(
                session=session,
                tenant_id=state["tenant_id"],
                product_name=product_name,
                category=category,
                searxng_url=str(settings.searxng_base_url),
            )
            await session.commit()

        await engine.dispose()

        if action_ids:
            result = (
                f"Discovery: found {len(action_ids)} potential supplier(s) for {category!r}. "
                f"Outreach drafts created (HITL). "
                f"Action IDs: {', '.join(action_ids)}. "
                "Awaiting importer approval — no emails sent."
            )
        else:
            result = (
                f"Discovery: no suitable suppliers found for {category!r}. "
                "Try a different category or product name."
            )

        new_action_ids = [*state.get("hitl_action_ids", []), *action_ids]

    except Exception as exc:
        logger.warning("discovery_specialist_failed", extra={"error": str(exc)})
        result = (
            f"Discovery error for {category!r}: {exc!s}. "
            "Manual search: POST /suppliers/discover"
        )
        new_action_ids = state.get("hitl_action_ids", [])

    return {
        **state,
        "specialist_result": result,
        "hitl_action_ids": new_action_ids,
        "messages": [*state["messages"], AIMessage(content=result)],
    }
