"""
Feature:  AI Agents — Communication Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.communication_agent
Purpose:  Drafts all outbound communications: supplier outreach, purchase orders,
          dispute letters, dunning messages (tone-classified), and fulfillment
          notifications. EVERY draft is submitted as a HITL action — this agent
          never sends directly. Action types created:
          - purchase_order_send: new PO drafted for supplier
          - supplier_outreach: new supplier contact email
          - dunning_disputes_on_demand: dispute letter
          - fulfillment_notification: consumer shipment update
          Reads task_description to decide which action_type to create.
Depends:  langgraph, app.infra.llm.openai, app.infra.db.repos.hitl_repo
HITL:     purchase_order_send, supplier_outreach, dunning_disputes_on_demand,
          fulfillment_notification
"""

from __future__ import annotations

import logging
import uuid

from app.agents.supervisor import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

# Keywords to action_type routing
_KEYWORD_ACTION_MAP = [
    (["purchase order", "po ", "reorder", "place order"], "purchase_order_send"),
    (["dispute", "chargeback", "claim", "challenge"], "dunning_disputes_on_demand"),
    (["fulfillment", "shipped", "delivered", "notify customer"], "fulfillment_notification"),
    (["outreach", "discover supplier", "contact supplier", "new supplier"], "supplier_outreach"),
]


def _detect_action_type(task: str) -> str:
    task_lower = task.lower()
    for keywords, action_type in _KEYWORD_ACTION_MAP:
        if any(kw in task_lower for kw in keywords):
            return action_type
    return "supplier_outreach"  # default for communication tasks


async def run(state: AgentState) -> AgentState:
    """
    Communication specialist node.
    Detects the required action type from the task description,
    drafts the message via GPT-4o, and creates a HITL action.
    Returns HITL action_id in specialist_result.
    Never sends any message directly.
    """
    task = state.get("task_description", "")
    messages_list = state.get("messages", [])
    last_msg = str(messages_list[-1].content) if messages_list else task

    action_type = _detect_action_type(task or last_msg)

    try:
        from app.infra.llm.openai import chat_completion  # noqa: PLC0415

        draft_prompt = (
            f"Draft a professional {action_type.replace('_', ' ')} message for the following task:\n"
            f"{task or last_msg}\n\n"
            "Keep it concise, professional, and in English. "
            "Do not include subject line — body only."
        )

        draft = await chat_completion(
            messages=[{"role": "user", "content": draft_prompt}],
            model="gpt-4o-mini",
            max_tokens=600,
            temperature=0.3,
        )

        # Create HITL action
        action_id = await _create_hitl_action(
            state=state,
            action_type=action_type,
            payload={
                "draft": draft,
                "task_description": task or last_msg,
                "drafted_by": "communication_agent",
            },
        )

        result = (
            f"Draft created for action_type={action_type!r}. "
            f"HITL action ID: {action_id}. "
            "Awaiting importer approval — no message sent."
        )
        new_action_ids = [*state.get("hitl_action_ids", []), action_id]

    except Exception as exc:
        logger.warning("communication_specialist_failed", extra={"error": str(exc)})
        action_id = f"error-{uuid.uuid4().hex[:8]}"
        result = f"Communication specialist error: {exc!s}. Draft not created."
        new_action_ids = state.get("hitl_action_ids", [])

    return {
        **state,
        "specialist_result": result,
        "hitl_action_ids": new_action_ids,
        "messages": [*state["messages"], AIMessage(content=result)],
    }


async def _create_hitl_action(
    state: AgentState,
    action_type: str,
    payload: dict[str, object],
) -> str:
    """Create a HITL action row. Returns the action_id."""
    try:
        from app.core.config import get_settings  # noqa: PLC0415
        from app.infra.db.repos.hitl_repo import HITLRepository  # noqa: PLC0415
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: PLC0415

        settings = get_settings()
        engine = create_async_engine(str(settings.database_url), echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            repo = HITLRepository(session, state["tenant_id"])
            action = await repo.create(
                action_id=uuid.uuid4().hex,
                action_type=action_type,
                payload=payload,
            )
            await session.commit()
            action_id = action.action_id

        await engine.dispose()
        return str(action_id)

    except Exception as exc:
        logger.warning("communication_hitl_create_failed", extra={"error": str(exc)})
        return f"hitl-pending-{uuid.uuid4().hex[:8]}"
