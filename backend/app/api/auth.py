"""
Feature:  Authentication & Tenant Onboarding
Layer:    API / Router
Module:   app.api.auth
Purpose:  HTTP routes for tenant self-signup, user login, JWT issuance,
          token refresh, and /auth/me (returns user + operational_mode).
          Triggers tenant provisioning workflow (n8n WF-01) on signup.
Depends:  app.core.auth.services, app.api.deps
HITL:     None — auth is not an external write action.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
