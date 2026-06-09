"""
Feature:  Dunning Engine (4 Tracks)
Layer:    Core / Domain Models
Module:   app.core.dunning.models
Purpose:  Pydantic v2 domain models for Invoice, DunningSequence, DunningAction,
          and ToneClassifierResult. All trigger dates computed from due_date
          (not invoice_date). Includes 4 track definitions with trigger offsets.
Depends:  pydantic
HITL:     All 8 dunning action_types.
"""

from enum import StrEnum

from pydantic import BaseModel


class DunningTrack(StrEnum):
    PAYABLES = "payables"  # Track 1: outbound to our suppliers
    DISPUTES = "disputes"  # Track 2: inbound from suppliers (Retail Only)
    RECEIVABLES = "receivables"  # Track 3: outbound to our B2B customers
    B2C = "b2c"  # Track 4: outbound to storefront customers


class ToneClass(StrEnum):
    GENTLE = "gentle"
    NEUTRAL = "neutral"
    FIRM = "firm"


class ToneClassifierResult(BaseModel):
    model_config = {"extra": "forbid"}

    tone: ToneClass
    confidence: float
    features: dict[str, float]


class InvoiceDomain(BaseModel):
    model_config = {"extra": "forbid"}

    invoice_id: str
    tenant_id: str
    direction: str  # payable | receivable
    amount_due: float
    invoice_date: str
    due_date: str  # All trigger dates computed from this field
    payment_terms_days: int
    paid_at: str | None = None
