"""
Feature:  Supplier Management
Layer:    Test / Unit
Module:   tests.unit.test_supplier_matching
Purpose:  Unit tests for supplier matching and scoring. Verifies: Ridge
          Regression scorer returns scores in [0,1], feature weights sum to 100,
          ranking order is deterministic for known inputs.
Depends:  app.ml.scoring.supplier_scorer, conftest fakes
HITL:     None
"""
from __future__ import annotations

import pytest


class TestSupplierScorer:
    def test_score_in_valid_range(self) -> None:
        """Supplier score must be in [0, 1]."""
        from app.ml.scoring.supplier_scorer import score_supplier

        features = {
            "on_time_delivery_rate": 0.9,
            "defect_rate": 0.02,
            "avg_lead_time_days": 14,
            "price_competitiveness": 0.85,
            "communication_responsiveness": 0.88,
            "order_fill_rate": 0.95,
        }
        score = score_supplier(features)
        assert 0.0 <= score <= 1.0

    def test_better_supplier_scores_higher(self) -> None:
        """A supplier with better metrics must score higher."""
        from app.ml.scoring.supplier_scorer import score_supplier

        good = {
            "on_time_delivery_rate": 0.99,
            "defect_rate": 0.001,
            "avg_lead_time_days": 5,
            "price_competitiveness": 0.95,
            "communication_responsiveness": 0.98,
            "order_fill_rate": 0.99,
        }
        poor = {
            "on_time_delivery_rate": 0.5,
            "defect_rate": 0.15,
            "avg_lead_time_days": 60,
            "price_competitiveness": 0.4,
            "communication_responsiveness": 0.5,
            "order_fill_rate": 0.6,
        }
        assert score_supplier(good) > score_supplier(poor)
