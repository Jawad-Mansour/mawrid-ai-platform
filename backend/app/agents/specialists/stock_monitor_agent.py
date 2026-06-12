"""
Feature:  AI Agents — Stock Monitor Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.stock_monitor_agent
Purpose:  Monitors inventory levels against reorder thresholds. Calls the
          Phase 7 trigger_reorder_check() service, which:
          1. Queries products WHERE qty_in_stock <= reorder_threshold
          2. Guards against duplicate pending PO HITL actions
          3. Selects best-scored supplier for each product
          4. Drafts PO via GPT-4o
          5. Creates purchase_order_send HITL action
          Returns count of HITL actions created in specialist_result.
Depends:  langgraph, app.core.suppliers.services, app.infra.db
HITL:     purchase_order_send (reorder trigger — one per under-threshold product)
"""

from __future__ import annotations

import logging

from app.agents.supervisor import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


async def run(state: AgentState) -> AgentState:
    """
    Stock Monitor specialist node.
    Runs the reorder check for the current tenant.
    Returns the count and IDs of HITL actions created.
    """
    try:
        from app.core.config import get_settings  # noqa: PLC0415
        from app.core.suppliers.services import trigger_reorder_check  # noqa: PLC0415
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

        settings = get_settings()
        engine = create_async_engine(str(settings.database_url), echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            action_ids = await trigger_reorder_check(session, state["tenant_id"])
            await session.commit()

        await engine.dispose()

        if action_ids:
            result = (
                f"Stock Monitor: {len(action_ids)} reorder HITL action(s) created. "
                f"Action IDs: {', '.join(action_ids[:5])}"
                + (" (and more...)" if len(action_ids) > 5 else ".")
                + " Awaiting importer approval — no POs sent."
            )
        else:
            result = (
                "Stock Monitor: all products are above reorder thresholds. "
                "No reorder actions needed at this time."
            )

        new_action_ids = [*state.get("hitl_action_ids", []), *action_ids]

    except Exception as exc:
        logger.warning("stock_monitor_specialist_failed", extra={"error": str(exc)})
        result = f"Stock Monitor error: {exc!s}. Manual check: POST /suppliers/reorder-check"
        new_action_ids = state.get("hitl_action_ids", [])

    return {
        **state,
        "specialist_result": result,
        "hitl_action_ids": new_action_ids,
        "messages": [*state["messages"], AIMessage(content=result)],
    }
