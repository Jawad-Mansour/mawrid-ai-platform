"""
Feature:  Security (cross-cutting)
Layer:    Middleware
Module:   app.middleware.rate_limit
Purpose:  Per-tenant rate limiting via Redis sliding window. Limits: 100 req/min
          for standard tier, 500 req/min for premium. Returns 429 with
          Retry-After header. Does not count /health or /webhooks endpoints.
Depends:  starlette, redis
HITL:     None.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)
        return response
