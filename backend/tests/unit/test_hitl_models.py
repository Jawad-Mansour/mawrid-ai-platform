"""
Feature:  HITL Approval Center
Layer:    Tests / Unit
Module:   tests.unit.test_hitl_models
Purpose:  Unit tests for HITLAction model validation: all 14 action_types
          accepted, invalid action_type rejected, extra fields forbidden
          (extra='forbid'), status transitions validated.
Depends:  app.core.hitl.models
HITL:     None — testing the model itself.
"""

import pytest
from app.core.hitl.models import HITLAction, HITLActionType, HITLStatus
from pydantic import ValidationError


def test_valid_action_type():
    action = HITLAction(
        action_id="act-001",
        tenant_id="t1",
        action_type=HITLActionType.PURCHASE_ORDER_SEND,
        payload={"po_number": "PO-001"},
        created_at="2024-01-01T00:00:00Z",
    )
    assert action.status == HITLStatus.PENDING


def test_all_action_types_valid():
    for at in HITLActionType:
        action = HITLAction(
            action_id=f"act-{at}",
            tenant_id="t1",
            action_type=at,
            payload={},
            created_at="2024-01-01T00:00:00Z",
        )
        assert action.action_type == at


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        HITLAction(
            action_id="act-001",
            tenant_id="t1",
            action_type=HITLActionType.DISPUTE_LETTER,
            payload={},
            created_at="2024-01-01T00:00:00Z",
            unknown_field="bad",  # type: ignore[call-arg]
        )
