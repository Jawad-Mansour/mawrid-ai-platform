"""
Feature:  Multi-Tenant Isolation (cross-cutting)
Layer:    Middleware
Module:   app.middleware.tenant
Purpose:  Extracts tenant_id from JWT and sets PostgreSQL RLS parameter
          app.current_tenant_id via SET LOCAL on every request session.
          This is the first of 3 isolation layers (RLS → TenantRepository
          → pgvector tenant filter).
Depends:  pyjwt, app.infra.db.session
HITL:     None.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Parse JWT → tenant_id
        # 2. SET LOCAL app.current_tenant_id = tenant_id on DB session
        # 3. Attach tenant_id to request.state
        response: Response = await call_next(request)
        return response
