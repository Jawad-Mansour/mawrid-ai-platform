"""
Feature:  Observability (cross-cutting)
Layer:    Middleware
Module:   app.middleware.logging
Purpose:  Structured JSON request logging: tenant_id, user_id, route, method,
          status_code, latency_ms on every response. Uses structlog for JSON
          output compatible with log aggregators (Loki, CloudWatch, etc.).
Depends:  starlette, structlog
HITL:     None.
"""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return response
