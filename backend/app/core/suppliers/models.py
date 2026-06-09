"""
Feature:  Supplier Intelligence
Layer:    Core / Domain Models
Module:   app.core.suppliers.models
Purpose:  Pydantic v2 domain models for Supplier, DeliveryEvent, SupplierScore,
          and MatchingCandidate. Supplier score is Ridge regression over 6 features:
          on_time_rate, damage_rate, avg_price_vs_market, response_time_hours,
          discrepancy_rate, data_completeness. Formula:
          Base 100 - (1-on_time)*40 - damage_rate*30 - max(0,price-1.0)*15
                   - (hours/168)*10 - (1-completeness)*5, clamped [0,100].
Depends:  pydantic
HITL:     supplier_outreach, supplier_match_review
"""

from pydantic import BaseModel, Field


class SupplierScore(BaseModel):
    model_config = {"extra": "forbid"}

    supplier_id: str
    score: float = Field(ge=0.0, le=100.0)
    on_time_rate: float
    damage_rate: float
    avg_price_vs_market: float
    response_time_hours: float
    discrepancy_rate: float
    data_completeness: float


class SupplierDomain(BaseModel):
    model_config = {"extra": "forbid"}

    supplier_id: str
    tenant_id: str
    name: str
    embedding_vector: list[float] | None = None
    score: SupplierScore | None = None
