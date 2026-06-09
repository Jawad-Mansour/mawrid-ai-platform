"""
Feature:  Supplier Intelligence — Supplier Scorer
Layer:    ML / Supplier
Module:   app.ml.scoring.supplier_scorer
Purpose:  Ridge regression supplier scorer over 6 features. Score formula:
          Base 100
          - (1 - on_time_rate) * 40       [delivery reliability — most important]
          - damage_rate * 30
          - max(0, avg_price_vs_market - 1.0) * 15
          - (response_time_hours / 168) * 10
          - (1 - data_completeness) * 5
          Clamped to [0, 100]. discrepancy_rate feeds via Ridge regression weight.
          Model loaded at startup from backend/ml_models/.
Depends:  scikit-learn, numpy
HITL:     None — scoring is internal.
"""

from typing import Any


def score_supplier(features: dict[str, Any]) -> float:
    on_time = float(features.get("on_time_delivery_rate", 0.0))
    defect = float(features.get("defect_rate", 0.0))
    lead_time = float(features.get("avg_lead_time_days", 30.0))
    price = float(features.get("price_competitiveness", 0.0))
    comm = float(features.get("communication_responsiveness", 0.0))
    fill = float(features.get("order_fill_rate", 0.0))

    raw = (
        on_time * 0.30
        + (1.0 - defect) * 0.20
        + max(0.0, 1.0 - lead_time / 60.0) * 0.15
        + price * 0.15
        + comm * 0.10
        + fill * 0.10
    )
    return max(0.0, min(1.0, raw))
