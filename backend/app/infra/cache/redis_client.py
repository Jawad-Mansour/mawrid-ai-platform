"""
Feature:  Infrastructure (cross-cutting — cache + rate limit + refresh tokens)
Layer:    Infra / Cache
Module:   app.infra.cache.redis_client
Purpose:  Async Redis client. Lazily initialized via init_redis() called from
          app lifespan. Used by rate limit middleware (sliding window), refresh
          token revocation (JTI tracking), and ARQ job queue.
Depends:  redis[asyncio], app.core.config
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

_redis: Any = None


async def init_redis(url: str) -> None:
    global _redis
    _redis = aioredis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]


def get_redis() -> Any:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() in lifespan.")
    return _redis


async def close_redis() -> None:
    if _redis is not None:
        await _redis.aclose()
