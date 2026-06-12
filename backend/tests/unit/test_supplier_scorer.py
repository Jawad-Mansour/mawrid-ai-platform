"""
Feature:  Supplier Intelligence — Scorer
Layer:    Tests / Unit
Module:   tests.unit.test_supplier_scorer
Purpose:  Unit tests for the deterministic supplier scoring formula.
          Tests all 6 penalty terms independently and boundary conditions.
          No DB or network required.
"""

from __future__ import annotations

import pytest
from app.ml.supplier_scorer.scorer import SupplierFeatures, compute_score_formula


def _perfect() -> SupplierFeatures:
    return SupplierFeatures(
        on_time_delivery_rate=1.0,
        damage_rate=0.0,
        avg_price_vs_market=1.0,
        response_time_hours=0.0,
        discrepancy_rate=0.0,
        catalog_completeness=1.0,
    )


class TestScoreFormula:
    def test_perfect_supplier_scores_100(self) -> None:
        assert compute_score_formula(_perfect()) == pytest.approx(100.0)

    def test_zero_on_time_rate_deducts_40(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=0.0,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(60.0)

    def test_half_on_time_deducts_20(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=0.5,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(80.0)

    def test_full_damage_rate_deducts_30(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=1.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(70.0)

    def test_price_at_market_no_penalty(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(100.0)

    def test_price_below_market_no_penalty(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=0.8,  # below market — bonus not applied
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(100.0)

    def test_price_50pct_over_deducts_75(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=1.5,  # max(0, 0.5) * 15 = 7.5
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(92.5)

    def test_one_week_response_deducts_10(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=168.0,  # exactly 1 week → min(1.0,1.0) * 10 = 10
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(90.0)

    def test_full_discrepancy_deducts_5(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=1.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) == pytest.approx(95.0)

    def test_zero_completeness_deducts_5(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=0.0,
        )
        assert compute_score_formula(f) == pytest.approx(95.0)

    def test_worst_case_clamped_to_zero(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=0.0,
            damage_rate=1.0,
            avg_price_vs_market=2.0,
            response_time_hours=168.0,
            discrepancy_rate=1.0,
            catalog_completeness=0.0,
        )
        assert compute_score_formula(f) == 0.0

    def test_extreme_values_clamped_to_zero(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=0.0,
            damage_rate=5.0,  # wildly above 1
            avg_price_vs_market=10.0,
            response_time_hours=10000.0,
            discrepancy_rate=5.0,
            catalog_completeness=0.0,
        )
        assert compute_score_formula(f) == 0.0

    def test_score_cannot_exceed_100(self) -> None:
        f = SupplierFeatures(
            on_time_delivery_rate=1.0,
            damage_rate=0.0,
            avg_price_vs_market=0.1,  # great price
            response_time_hours=0.0,
            discrepancy_rate=0.0,
            catalog_completeness=1.0,
        )
        assert compute_score_formula(f) <= 100.0
