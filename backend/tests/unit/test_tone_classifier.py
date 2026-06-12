"""
Feature:  Dunning Engine — Tone Classifier
Layer:    Tests / Unit
Module:   tests.unit.test_tone_classifier
Purpose:  Unit tests for tone classifier priority rules (P1→P4, first match wins).
          Covers: all 4 priority rules, rule precedence, boundary conditions,
          and the default neutral fallback. Tests run without ML model loaded —
          only rule-based paths are exercised.
Depends:  app.ml.tone.classifier
HITL:     None.
"""

from __future__ import annotations


class TestPriorityRule1:
    """P1: days_overdue <= 7 → gentle (overrides everything)."""

    def test_day_0_gentle(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=0,
            customer_segment="At-Risk",
            overdue_amount=5000.0,
            payment_history_score=0.1,
            previous_dunning_count=5,
        )
        assert result.tone == "gentle"
        assert result.confidence == 1.0

    def test_day_7_gentle(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=7,
            customer_segment="Dormant",
            overdue_amount=10000.0,
            payment_history_score=0.0,
            previous_dunning_count=10,
        )
        assert result.tone == "gentle"

    def test_day_8_not_p1(self) -> None:
        """Day 8 must not trigger P1."""
        from app.ml.tone.classifier import classify

        # Regular segment, bad score → neutral (not P1 gentle)
        result = classify(
            days_overdue=8,
            customer_segment="Regular",
            overdue_amount=500.0,
            payment_history_score=0.5,
            previous_dunning_count=0,
        )
        # P1 doesn't fire; P2 doesn't fire (Regular); P3 doesn't fire; P4 doesn't fire (score<0.8)
        assert result.tone == "neutral"

    def test_p1_beats_all_other_segments(self) -> None:
        """P1 fires before P2 check — even VIP at day 3 is still gentle (via P1, not P2)."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=3,
            customer_segment="VIP",
            overdue_amount=1000.0,
            payment_history_score=0.9,
            previous_dunning_count=0,
        )
        assert result.tone == "gentle"


class TestPriorityRule2:
    """P2: segment == 'VIP' → gentle (when days > 7)."""

    def test_vip_day_30_gentle(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=30,
            customer_segment="VIP",
            overdue_amount=50000.0,
            payment_history_score=0.2,
            previous_dunning_count=3,
        )
        assert result.tone == "gentle"
        assert result.confidence == 1.0

    def test_vip_day_90_gentle(self) -> None:
        """VIP stays gentle no matter how overdue."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=90,
            customer_segment="VIP",
            overdue_amount=100000.0,
            payment_history_score=0.0,
            previous_dunning_count=5,
        )
        assert result.tone == "gentle"

    def test_non_vip_day_30_not_p2(self) -> None:
        """Regular segment at day 30 with bad score → neutral (P2 doesn't fire)."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=30,
            customer_segment="Regular",
            overdue_amount=5000.0,
            payment_history_score=0.5,
            previous_dunning_count=0,
        )
        assert result.tone == "neutral"


class TestPriorityRule3:
    """P3: (At-Risk or Dormant) AND days >= 14 AND previous_dunning_count >= 2 → firm."""

    def test_atrisk_day14_dunning2_firm(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="At-Risk",
            overdue_amount=3000.0,
            payment_history_score=0.4,
            previous_dunning_count=2,
        )
        assert result.tone == "firm"
        assert result.confidence == 1.0

    def test_dormant_day21_dunning3_firm(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=21,
            customer_segment="Dormant",
            overdue_amount=8000.0,
            payment_history_score=0.3,
            previous_dunning_count=3,
        )
        assert result.tone == "firm"

    def test_atrisk_day13_not_p3(self) -> None:
        """Day 13 is below P3 threshold (need >= 14) — should be neutral."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=13,
            customer_segment="At-Risk",
            overdue_amount=2000.0,
            payment_history_score=0.4,
            previous_dunning_count=5,
        )
        # P1 doesn't fire (>7); P2 doesn't fire (not VIP); P3 doesn't fire (day<14); P4 doesn't fire
        assert result.tone == "neutral"

    def test_atrisk_day14_dunning1_not_p3(self) -> None:
        """At-Risk at day 14 but only 1 dunning attempt → P3 doesn't fire → neutral."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="At-Risk",
            overdue_amount=2000.0,
            payment_history_score=0.4,
            previous_dunning_count=1,
        )
        assert result.tone == "neutral"

    def test_regular_day14_dunning5_not_p3(self) -> None:
        """Regular segment can never trigger P3 (only At-Risk and Dormant)."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="Regular",
            overdue_amount=2000.0,
            payment_history_score=0.4,
            previous_dunning_count=5,
        )
        assert result.tone == "neutral"

    def test_p2_beats_p3(self) -> None:
        """VIP segment with P3-qualifying conditions → P2 fires first → gentle."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=30,
            customer_segment="VIP",
            overdue_amount=5000.0,
            payment_history_score=0.2,
            previous_dunning_count=5,
        )
        assert result.tone == "gentle"


class TestPriorityRule4:
    """P4: payment_history_score >= 0.8 → gentle (when P1/P2/P3 didn't fire)."""

    def test_regular_day20_high_score_gentle(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=20,
            customer_segment="Regular",
            overdue_amount=1500.0,
            payment_history_score=0.8,
            previous_dunning_count=0,
        )
        assert result.tone == "gentle"
        assert result.confidence == 1.0

    def test_atrisk_day14_dunning1_high_score_gentle(self) -> None:
        """At-Risk, day 14, only 1 dunning (P3 not triggered) but score >= 0.8 → gentle (P4)."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="At-Risk",
            overdue_amount=2000.0,
            payment_history_score=0.85,
            previous_dunning_count=1,
        )
        assert result.tone == "gentle"

    def test_score_0_79_not_p4(self) -> None:
        """Score 0.79 is below P4 threshold → neutral."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=20,
            customer_segment="Regular",
            overdue_amount=2000.0,
            payment_history_score=0.79,
            previous_dunning_count=0,
        )
        assert result.tone == "neutral"


class TestDefaultNeutral:
    """Default: when no priority rule fires → neutral."""

    def test_regular_day15_medium_score_neutral(self) -> None:
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=15,
            customer_segment="Regular",
            overdue_amount=3000.0,
            payment_history_score=0.5,
            previous_dunning_count=1,
        )
        assert result.tone == "neutral"

    def test_features_always_populated(self) -> None:
        """ToneClassifierResult.features must always have 5 keys."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=10,
            customer_segment="Regular",
            overdue_amount=1000.0,
            payment_history_score=0.5,
            previous_dunning_count=0,
        )
        assert "days_overdue" in result.features
        assert "payment_history_score" in result.features
        assert "overdue_amount" in result.features
        assert "previous_dunning_count" in result.features
        assert "customer_segment_encoded" in result.features


class TestRuleConsistency:
    """Verify classifier rules match generate_tone_data.py's determine_tone() exactly."""

    def test_boundary_p1_p3_interaction(self) -> None:
        """Day 7 At-Risk with 5 dunning counts: P1 fires before P3 → gentle."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=7,
            customer_segment="At-Risk",
            overdue_amount=10000.0,
            payment_history_score=0.1,
            previous_dunning_count=5,
        )
        assert result.tone == "gentle"  # P1 wins

    def test_atrisk_day14_dunning2_low_score_firm(self) -> None:
        """Classic P3 case — firm, not neutral despite low score (P3 beats default)."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="At-Risk",
            overdue_amount=5000.0,
            payment_history_score=0.3,
            previous_dunning_count=2,
        )
        assert result.tone == "firm"

    def test_p3_blocks_p4(self) -> None:
        """At-Risk + day 14 + 2 dunning BUT score >= 0.8: P3 fires before P4 → firm."""
        from app.ml.tone.classifier import classify

        result = classify(
            days_overdue=14,
            customer_segment="At-Risk",
            overdue_amount=5000.0,
            payment_history_score=0.95,  # Would trigger P4 if P3 didn't fire first
            previous_dunning_count=2,
        )
        assert result.tone == "firm"
