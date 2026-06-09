"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Core / Service
Module:   app.core.hitl.services
Purpose:  Business logic for HITL action lifecycle: create (any feature can call),
          approve (validates transition, enqueues execution), reject, edit (returns
          to pending), expire (background job). Single transaction guarantee:
          no external side effect fires before status='approved'.
Depends:  app.core.hitl.models, app.infra.db.repos.hitl_repo,
          app.infra.queue.client (ARQ for execution)
HITL:     This IS the HITL service.
"""
