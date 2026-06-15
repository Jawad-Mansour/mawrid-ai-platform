"""
Feature:  Model Health & Drift Detection
Layer:    Tests / Unit
Module:   tests.unit.test_drift_monitor
Purpose:  Unit tests for PSI, chi-square, cosine drift, and report aggregation.
          All tests are pure — no Docker, DB, or network required.
Depends:  app.ml.drift.monitor, numpy
HITL:     None.
"""

from __future__ import annotations

import numpy as np
import pytest
from app.ml.drift.monitor import (
    DriftResult,
    check_embedding_drift,
    check_intent_classifier_drift,
    check_tone_classifier_drift,
    compute_chi_square,
    compute_cosine_drift,
    compute_psi,
    run_drift_report,
)

# ── compute_psi ───────────────────────────────────────────────────────────────


class TestComputePsi:
    def test_identical_distributions_return_zero(self) -> None:
        rng = np.random.default_rng(0)
        data = rng.normal(0, 1, 1000)
        psi = compute_psi(data, data)
        assert psi < 0.01

    def test_stable_psi_below_warning_threshold(self) -> None:
        rng = np.random.default_rng(1)
        baseline = rng.normal(0, 1, 2000)
        current = rng.normal(0.05, 1, 2000)  # tiny mean shift
        psi = compute_psi(baseline, current)
        assert psi < 0.10

    def test_moderate_shift_above_stable_threshold(self) -> None:
        rng = np.random.default_rng(2)
        baseline = rng.normal(0, 1, 2000)
        current = rng.normal(0.4, 1, 2000)  # 0.4-sigma mean shift → above 0.10
        psi = compute_psi(baseline, current)
        assert psi >= 0.10

    def test_severe_shift_above_threshold(self) -> None:
        rng = np.random.default_rng(3)
        baseline = rng.normal(0, 1, 2000)
        current = rng.normal(4.0, 1, 2000)  # 4-sigma shift → clearly drifted
        psi = compute_psi(baseline, current)
        assert psi >= 0.20

    def test_empty_baseline_returns_zero(self) -> None:
        current = np.array([1.0, 2.0, 3.0])
        assert compute_psi(np.array([]), current) == 0.0

    def test_empty_current_returns_zero(self) -> None:
        baseline = np.array([1.0, 2.0, 3.0])
        assert compute_psi(baseline, np.array([])) == 0.0

    def test_constant_distribution_returns_zero(self) -> None:
        baseline = np.ones(100)
        current = np.ones(100)
        assert compute_psi(baseline, current) == 0.0

    def test_returns_non_negative(self) -> None:
        rng = np.random.default_rng(4)
        a = rng.uniform(0, 1, 500)
        b = rng.uniform(0.5, 1.5, 500)
        assert compute_psi(a, b) >= 0.0


# ── compute_chi_square ────────────────────────────────────────────────────────


class TestComputeChiSquare:
    def test_identical_distributions_high_p_value(self) -> None:
        counts = {"a": 100, "b": 200, "c": 150}
        stat, pval = compute_chi_square(counts, counts)
        assert pval > 0.05

    def test_heavily_shifted_distribution_low_p_value(self) -> None:
        baseline = {"cat": 300, "dog": 300, "fish": 300}
        current = {"cat": 500, "dog": 50, "fish": 50}  # massive shift
        stat, pval = compute_chi_square(baseline, current)
        assert pval < 0.01

    def test_missing_key_in_current_counts_as_zero(self) -> None:
        baseline = {"a": 100, "b": 100, "c": 100}
        current = {"a": 100, "b": 100}  # "c" missing → treated as 0
        stat, pval = compute_chi_square(baseline, current)
        assert stat >= 0.0

    def test_empty_baseline_returns_no_drift(self) -> None:
        stat, pval = compute_chi_square({}, {"a": 10})
        assert stat == 0.0
        assert pval == 1.0

    def test_returns_non_negative_statistic(self) -> None:
        baseline = {"intent_a": 80, "intent_b": 120}
        current = {"intent_a": 60, "intent_b": 140}
        stat, pval = compute_chi_square(baseline, current)
        assert stat >= 0.0
        assert 0.0 <= pval <= 1.0


# ── compute_cosine_drift ──────────────────────────────────────────────────────


class TestComputeCosineDrift:
    def test_identical_centroids_return_zero(self) -> None:
        v = np.ones(1536)
        assert compute_cosine_drift(v, v) == pytest.approx(0.0, abs=1e-6)

    def test_orthogonal_vectors_return_one(self) -> None:
        a = np.zeros(4)
        b = np.zeros(4)
        a[0] = 1.0
        b[1] = 1.0
        assert compute_cosine_drift(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_opposite_vectors_return_two(self) -> None:
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])
        assert compute_cosine_drift(a, b) == pytest.approx(2.0, abs=1e-6)

    def test_small_perturbation_returns_low_drift(self) -> None:
        rng = np.random.default_rng(10)
        base = rng.normal(0, 1, 1536)
        current = base + rng.normal(0, 0.01, 1536)  # tiny noise
        drift = compute_cosine_drift(base, current)
        assert drift < 0.10

    def test_zero_vector_returns_zero(self) -> None:
        a = np.zeros(128)
        b = np.ones(128)
        assert compute_cosine_drift(a, b) == 0.0


# ── check_intent_classifier_drift ────────────────────────────────────────────


class TestCheckIntentClassifierDrift:
    def test_stable_probabilities_all_ok(self) -> None:
        rng = np.random.default_rng(20)
        baseline = rng.dirichlet(np.ones(8), size=500)
        current = baseline + rng.normal(0, 0.001, baseline.shape)
        current = np.clip(current, 0, 1)
        results = check_intent_classifier_drift(baseline, current)
        assert len(results) == 8
        assert all(r.model_name == "intent_classifier" for r in results)
        assert all(r.metric_type == "psi" for r in results)
        assert all(r.status == "ok" for r in results)

    def test_severe_shift_detected(self) -> None:
        rng = np.random.default_rng(21)
        # baseline: uniform-ish; current: heavily skewed to class 0
        baseline = rng.dirichlet(np.ones(8), size=500)
        skewed = np.zeros((500, 8))
        skewed[:, 0] = 0.95
        skewed[:, 1:] = 0.05 / 7
        results = check_intent_classifier_drift(baseline, skewed)
        statuses = [r.status for r in results]
        assert "severe" in statuses or "warning" in statuses

    def test_with_label_counts_adds_chi_square_result(self) -> None:
        rng = np.random.default_rng(22)
        proba = rng.dirichlet(np.ones(8), size=100)
        baseline_counts = {f"cls_{i}": 100 for i in range(8)}
        drifted_counts = {f"cls_{i}": (500 if i == 0 else 10) for i in range(8)}
        results = check_intent_classifier_drift(proba, proba, baseline_counts, drifted_counts)
        chi_sq_results = [r for r in results if r.metric_type == "chi_square"]
        assert len(chi_sq_results) == 1
        assert chi_sq_results[0].status in ("warning", "severe")

    def test_empty_arrays_produce_no_psi_results(self) -> None:
        results = check_intent_classifier_drift(np.empty((0, 8)), np.empty((0, 8)))
        assert results == []


# ── check_tone_classifier_drift ──────────────────────────────────────────────


class TestCheckToneClassifierDrift:
    def test_stable_tone_probabilities_all_ok(self) -> None:
        rng = np.random.default_rng(30)
        baseline = rng.dirichlet(np.ones(3), size=200)
        current = baseline + rng.normal(0, 0.001, baseline.shape)
        current = np.clip(current, 0, 1)
        results = check_tone_classifier_drift(baseline, current)
        assert len(results) == 3
        assert all(r.model_name == "tone_classifier" for r in results)

    def test_severe_tone_drift_detected(self) -> None:
        rng = np.random.default_rng(31)
        baseline = rng.dirichlet(np.ones(3), size=200)
        all_firm = np.zeros((200, 3))
        all_firm[:, 2] = 1.0
        results = check_tone_classifier_drift(baseline, all_firm)
        statuses = {r.status for r in results}
        assert "severe" in statuses or "warning" in statuses


# ── check_embedding_drift ─────────────────────────────────────────────────────


class TestCheckEmbeddingDrift:
    def test_stable_embedding_is_ok(self) -> None:
        rng = np.random.default_rng(40)
        baseline = rng.normal(0, 1, 1536)
        current = baseline + rng.normal(0, 0.001, 1536)
        result = check_embedding_drift(baseline, current)
        assert result.status == "ok"
        assert result.metric_type == "cosine"

    def test_severe_embedding_drift_detected(self) -> None:
        a = np.ones(1536)
        b = -np.ones(1536)
        result = check_embedding_drift(a, b)
        assert result.status == "severe"
        assert result.metric_value >= 0.20

    def test_custom_model_name(self) -> None:
        v = np.ones(128)
        result = check_embedding_drift(v, v, model_name="custom_embedder")
        assert result.model_name == "custom_embedder"


# ── run_drift_report ──────────────────────────────────────────────────────────


class TestRunDriftReport:
    def test_empty_results_returns_ok(self) -> None:
        report = run_drift_report([])
        assert report.overall_status == "ok"
        assert report.results == []
        assert report.checked_models == []

    def test_all_ok_overall_is_ok(self) -> None:
        results = [
            DriftResult("m1", "psi", 0.05, "ok"),
            DriftResult("m2", "cosine", 0.03, "ok"),
        ]
        report = run_drift_report(results)
        assert report.overall_status == "ok"

    def test_any_warning_escalates_to_warning(self) -> None:
        results = [
            DriftResult("m1", "psi", 0.05, "ok"),
            DriftResult("m1", "psi", 0.15, "warning"),
        ]
        report = run_drift_report(results)
        assert report.overall_status == "warning"

    def test_any_severe_escalates_to_severe(self) -> None:
        results = [
            DriftResult("m1", "psi", 0.15, "warning"),
            DriftResult("m2", "cosine", 0.30, "severe"),
        ]
        report = run_drift_report(results)
        assert report.overall_status == "severe"

    def test_checked_models_deduped_and_sorted(self) -> None:
        results = [
            DriftResult("tone_classifier", "psi", 0.05, "ok"),
            DriftResult("intent_classifier", "psi", 0.06, "ok"),
            DriftResult("tone_classifier", "cosine", 0.02, "ok"),
        ]
        report = run_drift_report(results)
        assert report.checked_models == ["intent_classifier", "tone_classifier"]
