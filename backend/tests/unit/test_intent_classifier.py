"""
Feature:  AI Chatbot — 3-Tier Intent Classifier
Layer:    Tests / Unit
Module:   tests.unit.test_intent_classifier
Purpose:  Unit tests for the 3-tier intent classification cascade.
          Covers: routing table, Tier 1 predict (no LLM), classify_sync,
          escalation logic, and mocked-Tier-3 cascade. No real LLM calls.
Depends:  app.ml.intent.classifier, app.ml.intent.tier1
HITL:     None.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.ml.intent.classifier import (
    AGENT_INTENTS,
    DIRECT_QUERY_INTENTS,
    RAG_INTENTS,
    ClassificationResult,
    _route_for_intent,
    classify,
    classify_sync,
)
from app.ml.intent.tier1 import CONFIDENCE_THRESHOLD


class TestRouteForIntent:
    """Pure function — no model, no network."""

    def test_out_of_scope_rejected(self) -> None:
        assert _route_for_intent("out_of_scope") == "rejected"

    def test_product_search_rag(self) -> None:
        assert _route_for_intent("product_search") == "rag"

    @pytest.mark.parametrize(
        "intent",
        ["order_status", "stock_check", "shipment_status", "invoice_query", "dunning_action"],
    )
    def test_direct_query_intents(self, intent: str) -> None:
        assert _route_for_intent(intent) == "direct_query"

    def test_complex_task_agent(self) -> None:
        assert _route_for_intent("complex_task") == "agent"

    def test_unknown_label_defaults_rag(self) -> None:
        assert _route_for_intent("mystery_intent") == "rag"


class TestIntentSets:
    """Validate the intent set definitions are consistent."""

    def test_direct_query_set(self) -> None:
        expected = {
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
        }
        assert expected == DIRECT_QUERY_INTENTS

    def test_rag_set(self) -> None:
        assert "product_search" in RAG_INTENTS

    def test_agent_set(self) -> None:
        assert "complex_task" in AGENT_INTENTS

    def test_sets_are_disjoint(self) -> None:
        assert not (DIRECT_QUERY_INTENTS & RAG_INTENTS)
        assert not (DIRECT_QUERY_INTENTS & AGENT_INTENTS)
        assert not (RAG_INTENTS & AGENT_INTENTS)


class TestTier1Predict:
    """Test Tier 1 TF-IDF+LR predict() — cold-starts from eval_dataset, no LLM."""

    def test_predict_returns_valid_intent(self) -> None:
        from app.ml.intent.tier1 import INTENT_CLASSES, predict

        result = predict("show me all Samsung TVs")
        assert result.intent in INTENT_CLASSES
        assert 0.0 <= result.confidence <= 1.0
        assert result.latency_ms >= 0.0

    def test_escalate_flag_true_when_low_confidence(self) -> None:
        from app.ml.intent.tier1 import predict

        # Gibberish → Tier 1 will likely have low confidence
        result = predict("xyzzy frobble nonce quxqux")
        # escalate is tied to confidence threshold — just verify it reflects confidence
        assert result.escalate == (result.confidence < CONFIDENCE_THRESHOLD)

    def test_escalate_flag_false_when_high_confidence(self) -> None:
        # Use a very typical phrase — after training on eval_dataset it should hit >0.70
        from app.ml.intent.tier1 import predict

        # Mock a high-confidence result via _load_or_build patch
        mock_pipeline = MagicMock()
        import numpy as np

        proba = np.array([0.0, 0.0, 0.85, 0.0, 0.0, 0.0, 0.0, 0.15])  # stock_check at idx 2
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = predict("how many units in stock?")

        assert result.intent == "stock_check"
        assert result.confidence == pytest.approx(0.85)
        assert result.escalate is False

    def test_escalate_flag_when_confidence_at_threshold(self) -> None:
        from app.ml.intent.tier1 import predict

        mock_pipeline = MagicMock()
        import numpy as np

        proba = np.array([0.70, 0.30, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = predict("some query")

        # Exactly at threshold (0.70) → NOT escalated (< threshold, not <=)
        assert result.escalate is False
        assert result.confidence == pytest.approx(0.70)


class TestClassifySync:
    """classify_sync() uses only Tier 1 — no async, no LLM."""

    def test_returns_classification_result(self) -> None:
        result = classify_sync("what is the price of the Samsung fridge?")
        assert isinstance(result, ClassificationResult)
        assert result.tier_used == 1

    def test_route_assigned(self) -> None:
        mock_pipeline = MagicMock()
        import numpy as np

        proba = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.95])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = classify_sync("tell me a joke")

        assert result.intent == "out_of_scope"
        assert result.route == "rejected"


class TestClassifyCascade:
    """Test classify() cascade: Tier 1 → Tier 2 → Tier 3."""

    @pytest.mark.asyncio
    async def test_tier1_confident_no_escalation(self) -> None:
        """When Tier 1 is confident, cascade stops at Tier 1."""
        import numpy as np

        mock_pipeline = MagicMock()
        proba = np.array([0.95, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = await classify("show me Samsung TVs")

        assert result.tier_used == 1
        assert result.intent == "product_search"
        assert result.route == "rag"

    @pytest.mark.asyncio
    async def test_tier1_escalates_tier2_unavailable_falls_to_tier3(self) -> None:
        """Tier 1 escalates, Tier 2 returns None (unavailable), Tier 3 (mocked) resolves."""
        import numpy as np

        mock_pipeline = MagicMock()
        # Low confidence → escalate
        proba = np.array([0.2, 0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with (
            patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline),
            patch("app.ml.intent.tier2.predict", return_value=None),
            patch(
                "app.ml.intent.classifier._tier3_classify",
                new_callable=AsyncMock,
                return_value=("stock_check", 0.95, 350.0),
            ),
        ):
            result = await classify("how much stock do we have?")

        assert result.tier_used == 3
        assert result.intent == "stock_check"
        assert result.route == "direct_query"

    @pytest.mark.asyncio
    async def test_out_of_scope_route_is_rejected(self) -> None:
        import numpy as np

        mock_pipeline = MagicMock()
        proba = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.99])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = await classify("what is 2 + 2?")

        assert result.intent == "out_of_scope"
        assert result.route == "rejected"

    @pytest.mark.asyncio
    async def test_complex_task_routes_to_agent(self) -> None:
        import numpy as np

        mock_pipeline = MagicMock()
        proba = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.92, 0.08])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            result = await classify("find me a new supplier and draft an outreach email")

        assert result.intent == "complex_task"
        assert result.route == "agent"

    @pytest.mark.asyncio
    async def test_tier1_escalates_tier2_resolves(self) -> None:
        """Tier 1 escalates, Tier 2 is confident → cascade stops at Tier 2."""
        import numpy as np
        from app.ml.intent.tier2 import Tier2Result

        mock_pipeline = MagicMock()
        # Low confidence → escalate
        proba = np.array([0.3, 0.3, 0.1, 0.1, 0.05, 0.05, 0.05, 0.05])
        mock_pipeline.predict_proba.return_value = [proba]
        mock_pipeline.classes_ = [
            "product_search",
            "order_status",
            "stock_check",
            "shipment_status",
            "invoice_query",
            "dunning_action",
            "complex_task",
            "out_of_scope",
        ]

        t2_result = Tier2Result(
            intent="order_status",
            confidence=0.91,
            latency_ms=80.0,
            escalate=False,
        )

        with (
            patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline),
            patch("app.ml.intent.tier2.predict", return_value=t2_result),
        ):
            result = await classify("where is my order?")

        assert result.tier_used == 2
        assert result.intent == "order_status"
        assert result.route == "direct_query"
