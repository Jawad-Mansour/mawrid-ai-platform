"""
Feature:  AI Agents — State Persistence
Layer:    Agent
Module:   app.agents.checkpointer
Purpose:  AsyncRedisSaver setup for LangGraph agent state checkpointing.
          thread_id format: {tenant_id}:{user_id}:{session_uuid}.
          Ensures agent conversations survive network interruptions and server
          restarts. TTL: 24 hours per thread. Key prefix: "langgraph:ckpt:".
          Uses same Redis connection as ARQ job queue, different key namespace.
Depends:  langgraph-checkpoint-redis, redis, app.core.config
HITL:     None — state persistence only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

THREAD_ID_PATTERN = re.compile(
    r"^[a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-]+:[a-f0-9\-]{36}$"
)
CHECKPOINT_TTL_SECONDS = 86_400  # 24 hours


def make_thread_id(tenant_id: str, user_id: str, session_uuid: str) -> str:
    """Create a tenant-scoped thread ID. Format: {tenant_id}:{user_id}:{session_uuid}."""
    return f"{tenant_id}:{user_id}:{session_uuid}"


def validate_thread_id(thread_id: str) -> bool:
    """Validate thread_id format to prevent cross-tenant checkpoint collisions."""
    return bool(THREAD_ID_PATTERN.match(thread_id))


def get_tenant_from_thread(thread_id: str) -> str:
    """Extract tenant_id from thread_id. Raises ValueError on invalid format."""
    parts = thread_id.split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid thread_id format: {thread_id!r}")
    return parts[0]


@asynccontextmanager
async def checkpointer_scope() -> AsyncIterator[Any]:
    """
    Yield a ready-to-use LangGraph checkpointer for the duration of an agent run.

    AsyncRedisSaver.from_conn_string is itself an async context manager (it opens
    and closes the Redis connection), so it MUST be entered with `async with` and
    the saver used only inside that scope. This helper owns that lifecycle and
    falls back to an in-memory saver if Redis is unavailable.

    Usage:
        async with checkpointer_scope() as checkpointer:
            result = await run_agent(state, checkpointer=checkpointer)
    """
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    # AsyncExitStack owns the Redis connection lifecycle. The try/except wraps
    # ONLY creation + setup so the single `yield` always runs exactly once —
    # exceptions raised inside the caller's `async with` body propagate normally
    # and unwind the stack (closing Redis) without a double-yield.
    async with AsyncExitStack() as stack:
        saver: Any
        try:
            from langgraph.checkpoint.redis.aio import AsyncRedisSaver  # noqa: PLC0415

            saver = await stack.enter_async_context(
                AsyncRedisSaver.from_conn_string(
                    str(settings.redis_url),
                    ttl={"default": CHECKPOINT_TTL_SECONDS},
                )
            )
            await saver.asetup()
            logger.info(
                "langgraph_checkpointer_created", extra={"ttl": CHECKPOINT_TTL_SECONDS}
            )
        except Exception as exc:
            logger.error("langgraph_checkpointer_failed", extra={"error": str(exc)})
            from langgraph.checkpoint.memory import MemorySaver  # noqa: PLC0415

            logger.warning(
                "langgraph_using_memory_checkpointer — state will not persist "
                "across restarts"
            )
            saver = MemorySaver()

        yield saver
