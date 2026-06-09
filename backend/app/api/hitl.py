"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    API / Router
Module:   app.api.hitl
Purpose:  HTTP routes for listing pending HITL actions, approve, reject,
          edit (returns to pending), and history view with filters.
          This is the single approval surface for ALL action_types.
Depends:  app.core.hitl.services, app.api.deps
HITL:     This IS the HITL surface — all 14 action_types route through here.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/hitl", tags=["hitl"])
