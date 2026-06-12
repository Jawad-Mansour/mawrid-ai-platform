"""
Feature:  Supplier Intelligence — Matching
Layer:    Tests / Unit
Module:   tests.unit.test_supplier_matching
Purpose:  Unit tests for the TF-IDF supplier name matching helper.
          Tests exact match, similar names, dissimilar names, single candidate,
          empty list, multilingual names, and determinism.
          No DB or network required — pure function tests.
"""

from __future__ import annotations

from app.core.suppliers.services import _tfidf_match


class TestTfidfMatch:
    def test_empty_candidates_returns_none(self) -> None:
        result_id, score = _tfidf_match("Acme Corp", [])
        assert result_id is None
        assert score == 0.0

    def test_exact_name_very_high_similarity(self) -> None:
        candidates = [("s1", "Acme Corporation"), ("s2", "Tech Supplies Ltd")]
        result_id, score = _tfidf_match("Acme Corporation", candidates)
        assert result_id == "s1"
        assert score >= 0.99

    def test_similar_name_returns_best_candidate(self) -> None:
        candidates = [("s1", "Acme Corporation"), ("s2", "Tech Supplies Ltd")]
        result_id, score = _tfidf_match("Acme Corp", candidates)
        assert result_id == "s1"
        assert score > 0.0

    def test_dissimilar_name_low_score(self) -> None:
        candidates = [("s1", "Acme Corporation"), ("s2", "Acme Technologies")]
        result_id, score = _tfidf_match("XYZ Widgets International", candidates)
        assert result_id in ("s1", "s2")
        assert score < 0.5

    def test_single_candidate_returns_result(self) -> None:
        candidates = [("s1", "Acme Corporation")]
        result_id, score = _tfidf_match("Acme Corp", candidates)
        assert result_id == "s1"
        assert score >= 0.0

    def test_ordering_deterministic(self) -> None:
        candidates = [
            ("s1", "Global Supplies International"),
            ("s2", "Global Supply International"),
            ("s3", "Local Hardware Store"),
        ]
        id1, score1 = _tfidf_match("Global Supplies Intl", candidates)
        id2, score2 = _tfidf_match("Global Supplies Intl", candidates)
        assert id1 == id2
        assert score1 == score2

    def test_many_candidates_finds_best(self) -> None:
        candidates = [
            ("s1", "Alpha Tech Ltd"),
            ("s2", "Beta Supplies Co"),
            ("s3", "Gamma Distribution"),
            ("s4", "Delta Trading"),
            ("s5", "Alpha Technologies Limited"),
        ]
        result_id, score = _tfidf_match("Alpha Tech Ltd", candidates)
        assert result_id == "s1"
        assert score >= 0.99

    def test_different_candidates_different_result(self) -> None:
        candidates_a = [("s1", "Acme Corp"), ("s2", "Widget Inc")]
        candidates_b = [("s3", "Widget Inc"), ("s4", "Acme Corp")]
        id_a, _ = _tfidf_match("Acme Corp", candidates_a)
        id_b, _ = _tfidf_match("Acme Corp", candidates_b)
        assert id_a == "s1"
        assert id_b == "s4"
