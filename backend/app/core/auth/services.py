"""
Feature:  Authentication & Tenant Onboarding
Layer:    Core / Service
Module:   app.core.auth.services
Purpose:  Business logic for signup (tenant provisioning), login (argon2id
          password verification, RS256 JWT issuance), and token refresh.
          Calls n8n WF-01 webhook on successful signup.
Depends:  app.core.auth.models, app.infra.db.repos.tenant_repo, argon2-cffi, pyjwt
HITL:     None.
"""
