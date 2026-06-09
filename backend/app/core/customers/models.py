"""
Feature:  Customer Management
Layer:    Core / Domain Models
Module:   app.core.customers.models
Purpose:  Pydantic v2 domain models for Customer (B2B and B2C), MatchCandidate,
          and PaymentHistoryScore. Customer matching uses 3-tier waterfall:
          email exact → phone exact → name similarity (≥0.85 match, 0.3–0.85
          HITL, <0.3 auto-create new record).
Depends:  pydantic
HITL:     customer_match_review
"""

from enum import StrEnum

from pydantic import BaseModel, EmailStr


class CustomerType(StrEnum):
    B2B = "b2b"
    B2C = "b2c"


class CustomerDomain(BaseModel):
    model_config = {"extra": "forbid"}

    customer_id: str
    tenant_id: str
    customer_type: CustomerType
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    payment_history_score: float = 1.0  # 0.0–1.0
