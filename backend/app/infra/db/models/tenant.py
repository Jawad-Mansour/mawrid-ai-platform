"""
Feature:  Authentication & Tenant Onboarding
Layer:    Infra / DB Models
Module:   app.infra.db.models.tenant
Purpose:  SQLAlchemy ORM models for the `tenants` and `users` tables.
          Tenants is the root table — it has no tenant_id column itself
          (it IS the tenant). Users belong to a tenant. Role enum:
          admin | staff | viewer. Mode enum: Hybrid | Wholesale Only | Retail Only.
          Passwords stored as argon2id hashes. RS256 JWT issued on login.
Depends:  app.infra.db.base, sqlalchemy
HITL:     None — model only.
"""
