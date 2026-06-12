"""
Feature:  AI Agents — Supervisor Agent
Layer:    Agent
Module:   app.agents.supervisor
Purpose:  LangGraph Supervisor. Routes complex tasks to 5 specialist agents
          (Extraction, Enrichment, Communication, StockMonitor, Discovery).
          Bulk guard: tasks involving > 10 products pause for confirmation before
          executing. All write actions route to HITL — never executed directly.
          Checkpointed via AsyncRedisSaver; thread_id = {tenant_id}:{user_id}:{session_uuid}.
          State persists across server restarts — same thread_id resumes conversation.
Depends:  langgraph, langchain-openai, app.agents.specialists, app.agents.checkpointer
HITL:     All specialist write actions route through hitl_actions.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

BULK_GUARD_THRESHOLD = 10

# Specialist names used as LangGraph node names
SPECIALISTS = Literal[
    "extraction_specialist",
    "enrichment_specialist",
    "communication_specialist",
    "stock_monitor_specialist",
    "discovery_specialist",
]

ALL_SPECIALISTS: list[str] = [
    "extraction_specialist",
    "enrichment_specialist",
    "communication_specialist",
    "stock_monitor_specialist",
    "discovery_specialist",
]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: str
    user_id: str
    thread_id: str
    task_description: str
    intent: str
    active_specialist: str | None
    specialist_result: str | None
    hitl_action_ids: list[str]
    bulk_pending: bool
    estimated_product_count: int
    step_count: int
    finished: bool
    error: str | None


_SYSTEM_PROMPT = """You are the Supervisor for a B2B operations platform.
Your job is to route the user's task to the correct specialist agent.

Available specialists:
- extraction_specialist: process/parse supplier catalog documents, queue ARQ extraction jobs
- enrichment_specialist: enrich products with descriptions, specs, and images via the pipeline
- communication_specialist: draft emails, purchase orders, dunning messages (all HITL — never sends directly)
- stock_monitor_specialist: check stock levels, trigger reorder signals, create PO drafts
- discovery_specialist: find new suppliers via web search, draft outreach emails

Reply with exactly one word: the specialist name to invoke, or "done" if the task is complete.
Use "done" only when specialist_result already contains a satisfactory answer."""


async def supervisor_node(state: AgentState) -> Command[Any]:
    """Supervisor: decides which specialist to invoke next."""
    messages = state["messages"]
    specialist_result = state.get("specialist_result")
    step_count = state.get("step_count", 0)

    # Safety: max 10 supervisor steps
    if step_count >= 10 or state.get("finished"):
        final_msg = specialist_result or "Task completed."
        return Command(
            update={
                "messages": [AIMessage(content=final_msg)],
                "finished": True,
            },
            goto=END,
        )

    # Bulk guard: if estimated_product_count > threshold and not yet confirmed
    if state.get("bulk_pending"):
        count = state.get("estimated_product_count", 0)
        msg = (
            f"This task affects {count} products. "
            "Please confirm you want to proceed with this bulk operation. "
            "Reply 'yes' to continue or 'no' to cancel."
        )
        return Command(
            update={
                "messages": [AIMessage(content=msg)],
                "step_count": step_count + 1,
            },
            goto=END,
        )

    # Build context for the supervisor LLM call
    context_parts: list[str] = [
        f"Task: {state.get('task_description', messages[-1].content if messages else '')}",
    ]
    if specialist_result:
        context_parts.append(f"Last specialist result: {specialist_result}")

    try:
        from app.infra.llm.openai import chat_completion  # noqa: PLC0415

        raw = await chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(context_parts)},
            ],
            model="gpt-4o-mini",
            max_tokens=20,
            temperature=0.0,
        )
        decision = raw.strip().lower().replace("-", "_")
    except Exception as exc:
        logger.error("supervisor_llm_failed", extra={"error": str(exc)})
        decision = "done"

    if decision in ("done", "finish", "complete"):
        final = specialist_result or "Task completed successfully."
        return Command(
            update={
                "messages": [AIMessage(content=final)],
                "finished": True,
                "step_count": step_count + 1,
            },
            goto=END,
        )

    if decision in ALL_SPECIALISTS:
        return Command(
            update={
                "active_specialist": decision,
                "step_count": step_count + 1,
            },
            goto=decision,
        )

    # Unknown decision → end gracefully
    return Command(
        update={
            "messages": [AIMessage(content=specialist_result or "Task completed.")],
            "finished": True,
            "step_count": step_count + 1,
        },
        goto=END,
    )


def _build_graph() -> StateGraph[AgentState]:
    from app.agents.specialists.communication_agent import run as communication_run  # noqa: PLC0415
    from app.agents.specialists.discovery_agent import run as discovery_run  # noqa: PLC0415
    from app.agents.specialists.enrichment_agent import run as enrichment_run  # noqa: PLC0415
    from app.agents.specialists.extraction_agent import run as extraction_run  # noqa: PLC0415
    from app.agents.specialists.stock_monitor_agent import run as stock_monitor_run  # noqa: PLC0415

    graph: StateGraph[AgentState] = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("extraction_specialist", extraction_run)
    graph.add_node("enrichment_specialist", enrichment_run)
    graph.add_node("communication_specialist", communication_run)
    graph.add_node("stock_monitor_specialist", stock_monitor_run)
    graph.add_node("discovery_specialist", discovery_run)

    graph.add_edge(START, "supervisor")

    # All specialists return to supervisor for next decision
    for specialist in ALL_SPECIALISTS:
        graph.add_edge(specialist, "supervisor")

    return graph


async def run_agent(
    state: AgentState,
    checkpointer: Any | None = None,
) -> AgentState:
    """
    Run the supervisor graph with the given initial state.
    If checkpointer is provided, state is persisted across calls.

    Usage:
        result = await run_agent(
            AgentState(
                messages=[HumanMessage(content="Find a new appliance supplier")],
                tenant_id="t1",
                user_id="u1",
                thread_id="t1:u1:uuid-...",
                task_description="Find a new appliance supplier",
                intent="complex_task",
                active_specialist=None,
                specialist_result=None,
                hitl_action_ids=[],
                bulk_pending=False,
                estimated_product_count=0,
                step_count=0,
                finished=False,
                error=None,
            ),
            checkpointer=checkpointer,
        )
    """
    graph = _build_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    config: dict[str, Any] = {}
    if state.get("thread_id"):
        config = {"configurable": {"thread_id": state["thread_id"]}}

    result: AgentState = await compiled.ainvoke(state, config=config)  # type: ignore[call-overload]
    return result
