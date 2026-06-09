"""
Feature:  HITL Approval Center
Layer:    Tests / Integration
Module:   tests.integration.test_hitl_flow
Purpose:  Integration tests for full HITL lifecycle: create → approve → executed,
          create → reject, create → edit → pending → approve, expiry. Verifies
          no external side effect fires before status='approved'. Tests all 14
          action_types. Requires real DB.
Depends:  pytest-asyncio, app.core.hitl.services, app.infra.db
HITL:     None — testing the HITL system itself.
"""
