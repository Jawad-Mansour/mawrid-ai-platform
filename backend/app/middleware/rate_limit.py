"""
Feature:  Security (cross-cutting)
Layer:    Middleware
Module:   app.middleware.rate_limit
Purpose:  Per-tenant sliding window rate limiting via Redis. 100 req/min for
          standard tenants, 500 req/min for premium (tenant metadata TBD in
          Phase 7). Returns 429 with Retry-After header on breach.
          /health and /api/v1/webhooks paths are exempt.
Depends:  starlette, redis[asyncio]
HITL:     None.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_EXEMPT_PREFIXES = ("/health", "/api/v1/webhooks")
_WINDOW_SECONDS = 60
_STANDARD_LIMIT = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        tenant_id: str | None = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            return await call_next(request)

        try:
            from app.infra.cache.redis_client import get_redis

            redis = get_redis()
            window = int(time.time()) // _WINDOW_SECONDS
            key = f"rl:{tenant_id}:{window}"

            count: int = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _WINDOW_SECONDS * 2)

            if count > _STANDARD_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Retry after 60 seconds."},
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
        except Exception:
            # Redis unavailable — fail open (don't block requests)
            pass

        return await call_next(request)
