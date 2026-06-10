"""
Feature:  Multi-Tenant Isolation (cross-cutting)
Layer:    Middleware
Module:   app.middleware.tenant
Purpose:  Extracts tenant_id from JWT Bearer token and attaches it to
          request.state.tenant_id. Public paths (signup, login, health,
          JWKS) are exempt. The actual RLS SET LOCAL is applied per
          DB session in get_db_session() not here, to avoid opening a
          connection on every request.
Depends:  pyjwt, starlette
HITL:     None.
"""

from __future__ import annotations

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_PUBLIC_PATHS = {
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/.well-known/jwks.json",
    "/health",
}

# Public key is loaded lazily from vault secrets (set after lifespan boots)
_PUBLIC_KEY: str | None = None


def set_jwt_public_key(key: str) -> None:
    global _PUBLIC_KEY
    _PUBLIC_KEY = key


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.tenant_id = None
        request.state.user_id = None
        request.state.role = None

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and _PUBLIC_KEY:
            token = auth_header[7:]
            try:
                payload = jwt.decode(token, _PUBLIC_KEY, algorithms=["RS256"])
                request.state.tenant_id = payload.get("tenant_id")
                request.state.user_id = payload.get("sub")
                request.state.role = payload.get("role")
            except jwt.InvalidTokenError:
                pass

        return await call_next(request)
