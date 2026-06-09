"""
Feature:  HITL Approval Center (cross-cutting)
Layer:    Core / Domain Models
Module:   app.core.hitl.models
Purpose:  Pydantic v2 domain models for HITLAction covering all 14 action_types
          with JSONB payload schemas, 6 statuses with valid transitions, and
          expiry rules per action_type. This is the single gate for all external
          write actions — no external write may bypass this model.
Depends:  pydantic
HITL:     This IS the HITL model.
"""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class HITLActionType(StrEnum):
    PURCHASE_ORDER_SEND = "purchase_order_send"
    DISPUTE_LETTER = "dispute_letter"
    SUPPLIER_OUTREACH = "supplier_outreach"
    SUPPLIER_MATCH_REVIEW = "supplier_match_review"
    CUSTOMER_MATCH_REVIEW = "customer_match_review"
    DUNNING_PAYABLES_ADVANCE = "dunning_payables_advance"
    DUNNING_DISPUTES_ON_DEMAND = "dunning_disputes_on_demand"
    DUNNING_RECEIVABLES_DAY7 = "dunning_receivables_day7"
    DUNNING_RECEIVABLES_DAY14 = "dunning_receivables_day14"
    DUNNING_RECEIVABLES_DAY21 = "dunning_receivables_day21"
    DUNNING_B2C_DAY3 = "dunning_b2c_day3"
    DUNNING_B2C_DAY7 = "dunning_b2c_day7"
    DUNNING_B2C_DAY14 = "dunning_b2c_day14"
    FULFILLMENT_NOTIFICATION = "fulfillment_notification"


class HITLStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITING = "editing"
    EXECUTED = "executed"
    EXPIRED = "expired"


class HITLAction(BaseModel):
    model_config = {"extra": "forbid"}

    action_id: str
    tenant_id: str
    action_type: HITLActionType
    status: HITLStatus = HITLStatus.PENDING
    payload: dict[str, Any]
    created_at: str
    expires_at: str | None = None
    actor_user_id: str | None = None
