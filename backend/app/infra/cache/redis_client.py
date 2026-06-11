"""
Feature:  Infrastructure (cross-cutting — cache + rate limit + refresh tokens)
Layer:    Infra / Cache
Module:   app.infra.cache.redis_client
Purpose:  Async Redis client. Lazily initialized via init_redis() called from
          app lifespan. Used by rate limit middleware (sliding window), refresh
          token revocation (JTI tracking), and ARQ job queue.
Depends:  redis[asyncio], arq, app.core.config
HITL:     None — infrastructure only.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

_redis: Any = None
_arq_pool: ArqRedis | None = None


async def init_redis(url: str) -> None:
    global _redis, _arq_pool
    _redis = aioredis.from_url(url, decode_responses=True)  # type: ignore[no-untyped-call]
    _arq_pool = await create_pool(RedisSettings.from_dsn(url))


def get_redis() -> Any:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() in lifespan.")
    return _redis


def get_arq_pool() -> ArqRedis:
    if _arq_pool is None:
        raise RuntimeError("ARQ pool not initialized. Call init_redis() in lifespan.")
    return _arq_pool


async def close_redis() -> None:
    global _redis, _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
    if _redis is not None:
        await _redis.aclose()
