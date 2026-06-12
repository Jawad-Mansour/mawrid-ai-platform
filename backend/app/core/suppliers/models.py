"""
Feature:  Supplier Intelligence
Layer:    Core / Domain Models
Module:   app.core.suppliers.models
Purpose:  Pydantic v2 domain models for Supplier, DeliveryEventInput,
          SupplierMatchResult, and DiscoveryCandidate.
          Supplier score uses Ridge regression over 6 delivery features.
          Matching waterfall: exact → TF-IDF ≥ 0.9 → embedding ≥ 0.9 →
          0.3–0.9 HITL → <0.3 HITL "create new?".
Depends:  pydantic
HITL:     supplier_match_review, supplier_outreach
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeliveryEventInput(BaseModel):
    model_config = {"extra": "forbid"}

    order_id: str | None = None
    promised_date: str           # ISO date YYYY-MM-DD
    delivered_date: str | None = None
    items_ordered: int = Field(default=1, ge=1)
    items_received: int = Field(default=0, ge=0)
    items_damaged: int = Field(default=0, ge=0)
    price_agreed: float = Field(default=0.0, ge=0.0)
    price_billed: float | None = None
    response_time_hours: float | None = None
    notes: str | None = None


class SupplierMatchResult(BaseModel):
    model_config = {"extra": "forbid"}

    match_type: str           # "exact" | "tfidf" | "embedding" | "hitl" | "no_match"
    supplier_id: str | None   # set for auto-links; None when HITL pending
    confidence: float         # 0.0–1.0
    hitl_action_id: str | None = None


class DiscoveryCandidate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    website: str | None = None
    snippet: str | None = None
