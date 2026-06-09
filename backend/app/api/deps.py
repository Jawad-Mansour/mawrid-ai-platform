"""
Feature:  Auth & Dependency Injection (cross-cutting)
Layer:    API / Dependencies
Module:   app.api.deps
Purpose:  FastAPI Depends() providers: JWT parsing, tenant_id extraction,
          DB async session, repository injection, current user resolution,
          operational mode gate (require_mode).
Depends:  app.infra.db.session, app.core.auth.models
HITL:     None — infrastructure only.
"""
