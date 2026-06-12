"""
Feature:  AI Agents — Extraction Specialist
Layer:    Agent / Specialist
Module:   app.agents.specialists.extraction_agent
Purpose:  Queues an ARQ enrichment job for a supplier document. Wraps the
          Phase 2 sequential pipeline: parse → extract → enrich.
          Reads document_id from state task_description or messages.
          Enqueues via the ARQ worker. Returns job_id in specialist_result.
          Does NOT call the pipeline directly — delegates to async worker.
Depends:  langgraph, app.infra.workers.enrichment_worker, arq
HITL:     None — extraction is an internal pipeline step.
"""

from __future__ import annotations

import logging
import re

from app.agents.supervisor import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

_DOC_ID_RE = re.compile(r"\b([a-f0-9]{64})\b", re.IGNORECASE)


async def run(state: AgentState) -> AgentState:
    """
    Extraction specialist node. Extracts document_id from the task description
    and enqueues an ARQ enrichment job for it.
    Returns updated state with specialist_result containing the job_id.
    """
    task = state.get("task_description", "")
    messages = state.get("messages", [])
    last_msg = str(messages[-1].content) if messages else task

    # Try to find a document_id (SHA-256 hex) in the task or messages
    match = _DOC_ID_RE.search(task) or _DOC_ID_RE.search(last_msg)
    document_id = match.group(1) if match else None

    if not document_id:
        result = (
            "Extraction specialist: no document_id found in task. "
            "Please provide a document_id (SHA-256 hash of the uploaded file)."
        )
        return {
            **state,
            "specialist_result": result,
            "messages": [*state["messages"], AIMessage(content=result)],
        }

    try:
        import arq  # noqa: PLC0415
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(str(settings.redis_url)))
        job = await pool.enqueue_job(
            "enrich_document",
            document_id=document_id,
            tenant_id=state["tenant_id"],
        )
        job_id = getattr(job, "job_id", "unknown") if job else "unknown"
        await pool.aclose()

        result = (
            f"Extraction job queued. "
            f"Document: {document_id[:12]}... | ARQ Job: {job_id}"
        )
    except Exception as exc:
        logger.warning("extraction_specialist_arq_failed", extra={"error": str(exc)})
        result = (
            f"Extraction request received for document {document_id[:12]}... "
            f"(queue manually via POST /catalog/documents/{document_id}/enrich)"
        )

    return {
        **state,
        "specialist_result": result,
        "messages": [*state["messages"], AIMessage(content=result)],
    }
