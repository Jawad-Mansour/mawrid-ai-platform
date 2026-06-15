"""
Feature:  Customer Management
Layer:    Core / Domain Models
Module:   app.core.customers.models
Purpose:  Pydantic v2 domain models for Customer (B2B and B2C),
          CustomerMatchResult, and PaymentHistoryScore.
          Matching waterfall: email exact (1.0) → phone exact (0.95) →
          name TF-IDF ≥ 0.85 auto-link → 0.3–0.85 HITL → <0.3 auto-create.
          payment_history_score updated via rolling average on each payment.
Depends:  pydantic
HITL:     customer_match_review
"""

from __future__ import annotations

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


class CustomerMatchResult(BaseModel):
    model_config = {"extra": "forbid"}

    match_type: str  # "email" | "phone" | "name_tfidf" | "hitl" | "created"
    customer_id: str | None  # set for auto-links and new records; None while HITL pending
    confidence: float  # 0.0–1.0
    created: bool = False  # True when a brand-new customer record was inserted
    hitl_action_id: str | None = None
