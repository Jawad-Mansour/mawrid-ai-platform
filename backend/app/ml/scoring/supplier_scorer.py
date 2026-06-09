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
