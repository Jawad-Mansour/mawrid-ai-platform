"""
Feature:  Customer Management — Matching
Layer:    Tests / Unit
Module:   tests.unit.test_customer_matching
Purpose:  Unit tests for TF-IDF customer name matching and payment history
          score rolling average. Pure function tests — no DB or network.
"""

from __future__ import annotations

import pytest
from app.core.customers.services import _tfidf_name_match, compute_new_payment_score


class TestTfidfNameMatch:
    def test_empty_candidates_returns_none(self) -> None:
        result_id, score = _tfidf_name_match("John Smith", [])
        assert result_id is None
        assert score == 0.0

    def test_exact_name_very_high_similarity(self) -> None:
        candidates = [("c1", "John Smith"), ("c2", "Jane Doe")]
        result_id, score = _tfidf_name_match("John Smith", candidates)
        assert result_id == "c1"
        assert score >= 0.99

    def test_similar_name_returns_closest(self) -> None:
        candidates = [("c1", "Mohammed Al Hassan"), ("c2", "Alice Johnson")]
        result_id, score = _tfidf_name_match("Mohamed Al-Hassan", candidates)
        assert result_id == "c1"

    def test_dissimilar_name_low_score(self) -> None:
        candidates = [("c1", "John Smith"), ("c2", "Jane Doe")]
        result_id, score = _tfidf_name_match("Zhu Wei", candidates)
        assert score < 0.5

    def test_single_candidate_returns_result(self) -> None:
        candidates = [("c1", "John Smith")]
        result_id, score = _tfidf_name_match("John Smith", candidates)
        assert result_id == "c1"
        assert score >= 0.99

    def test_deterministic_results(self) -> None:
        candidates = [("c1", "Karim Mansour"), ("c2", "Sara Ali"), ("c3", "Yousef Hassan")]
        id1, s1 = _tfidf_name_match("Kareem Mansour", candidates)
        id2, s2 = _tfidf_name_match("Kareem Mansour", candidates)
        assert id1 == id2
        assert s1 == s2

    def test_picks_better_of_two_similar(self) -> None:
        candidates = [("c1", "Acme Trading Co"), ("c2", "Acme Trading Company")]
        result_id, score = _tfidf_name_match("Acme Trading Company", candidates)
        assert result_id == "c2"
        assert score >= 0.99


class TestPaymentHistoryScore:
    def test_first_payment_on_time(self) -> None:
        # (old_score * 0 + 1.0) / 1 = 1.0
        new_score = compute_new_payment_score(old_score=1.0, n=0, outcome=1.0)
        assert new_score == pytest.approx(1.0)

    def test_first_payment_after_dunning(self) -> None:
        # (1.0 * 0 + 0.0) / 1 = 0.0
        new_score = compute_new_payment_score(old_score=1.0, n=0, outcome=0.0)
        assert new_score == pytest.approx(0.0)

    def test_rolling_average_three_payments(self) -> None:
        # 2 on-time payments → score=1.0, third after dunning:
        # (1.0 * 2 + 0.0) / 3 ≈ 0.667
        new_score = compute_new_payment_score(old_score=1.0, n=2, outcome=0.0)
        assert new_score == pytest.approx(2.0 / 3.0, abs=1e-6)

    def test_late_payment_counts_05(self) -> None:
        # first payment late: (1.0 * 0 + 0.5) / 1 = 0.5
        new_score = compute_new_payment_score(old_score=1.0, n=0, outcome=0.5)
        assert new_score == pytest.approx(0.5)

    def test_score_clamped_above_zero(self) -> None:
        new_score = compute_new_payment_score(old_score=0.0, n=10, outcome=0.0)
        assert new_score >= 0.0

    def test_score_clamped_below_one(self) -> None:
        new_score = compute_new_payment_score(old_score=1.0, n=100, outcome=1.0)
        assert new_score <= 1.0
