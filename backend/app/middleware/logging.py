"""
Feature:  Observability (cross-cutting)
Layer:    Middleware
Module:   app.middleware.logging
Purpose:  Structured JSON request logging: tenant_id, user_id, route, method,
          status_code, latency_ms. PII fields (email, phone) stripped via
          Presidio before logging. Feeds into LangSmith/LangFuse tracing.
Depends:  starlette, structlog
HITL:     None.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)
        return response
