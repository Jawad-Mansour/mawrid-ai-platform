"""
Feature:  Multi-Tenant Isolation
Layer:    Tests / Integration
Module:   tests.integration.test_cross_tenant
Purpose:  Integration tests for all 3 isolation layers. Verifies tenant A
          cannot read tenant B's products, HITL actions, invoices, or embeddings.
          Tests run against real PostgreSQL (no mocks — per constitution.md).
          Covers 15 attack vectors from check-tenant.md skill.
Depends:  pytest-asyncio, sqlalchemy, app.infra.db
HITL:     None — testing isolation itself.
"""
