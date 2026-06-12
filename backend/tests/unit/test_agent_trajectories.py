"""
Feature:  AI Agents — CI Gate 6: Agent Trajectory Snapshots
Layer:    Tests / Unit
Module:   tests.unit.test_agent_trajectories
Purpose:  Verify that all 20 golden-path trajectories are routed correctly by
          the 3-tier intent classifier. Mocked Tier 1 pipeline per test case so
          no real LLM calls are made. Validates:
          - intent classification result
          - routing decision (rag / direct_query / agent / rejected)
          These are structural contract tests — they don't run the full agent.
Depends:  app.ml.intent.classifier, app.ml.intent.tier1
HITL:     None — routing only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

TRAJECTORIES_PATH = (
    Path(__file__).parent.parent / "evals" / "agent_trajectories" / "trajectories.json"
)

# Map expected_intent to class index in INTENT_CLASSES
_INTENT_TO_IDX: dict[str, int] = {
    "product_search": 0,
    "order_status": 1,
    "stock_check": 2,
    "shipment_status": 3,
    "invoice_query": 4,
    "dunning_action": 5,
    "complex_task": 6,
    "out_of_scope": 7,
}

_CLASSES = [
    "product_search",
    "order_status",
    "stock_check",
    "shipment_status",
    "invoice_query",
    "dunning_action",
    "complex_task",
    "out_of_scope",
]


def _load_trajectories() -> list[dict[str, Any]]:
    assert TRAJECTORIES_PATH.exists(), f"Trajectories file not found: {TRAJECTORIES_PATH}"
    data: list[dict[str, Any]] = json.loads(TRAJECTORIES_PATH.read_text(encoding="utf-8"))
    return data


def _make_mock_pipeline(expected_intent: str) -> MagicMock:
    """Create a mock sklearn pipeline that returns high-confidence for the given intent."""
    idx = _INTENT_TO_IDX[expected_intent]
    proba = np.zeros(8)
    proba[idx] = 0.95
    proba[(idx + 1) % 8] = 0.05

    mock = MagicMock()
    mock.predict_proba.return_value = [proba]
    mock.classes_ = _CLASSES
    return mock


class TestTrajectoryFileExists:
    """Sanity: the trajectory snapshot file exists and has the expected count."""

    def test_trajectories_file_exists(self) -> None:
        assert TRAJECTORIES_PATH.exists()

    def test_twenty_trajectories(self) -> None:
        trajectories = _load_trajectories()
        assert len(trajectories) == 20

    def test_all_have_required_fields(self) -> None:
        trajectories = _load_trajectories()
        required = {"id", "query", "expected_intent", "expected_route"}
        for t in trajectories:
            missing = required - set(t.keys())
            assert not missing, f"{t['id']} missing fields: {missing}"

    def test_all_ids_unique(self) -> None:
        trajectories = _load_trajectories()
        ids = [t["id"] for t in trajectories]
        assert len(ids) == len(set(ids))

    def test_all_intents_valid(self) -> None:
        valid_intents = set(_INTENT_TO_IDX.keys())
        trajectories = _load_trajectories()
        for t in trajectories:
            assert t["expected_intent"] in valid_intents, (
                f"{t['id']}: unknown intent {t['expected_intent']!r}"
            )

    def test_all_routes_valid(self) -> None:
        valid_routes = {"rag", "direct_query", "agent", "rejected"}
        trajectories = _load_trajectories()
        for t in trajectories:
            assert t["expected_route"] in valid_routes, (
                f"{t['id']}: unknown route {t['expected_route']!r}"
            )


class TestClassifierRoutingPerTrajectory:
    """
    For each trajectory: mock Tier 1 to return the expected intent with high
    confidence (0.95) → classifier resolves at Tier 1 → verify intent and route.
    """

    def _run_classify_sync(self, expected_intent: str) -> Any:
        from app.ml.intent.classifier import classify_sync

        mock_pipeline = _make_mock_pipeline(expected_intent)
        with patch("app.ml.intent.tier1._load_or_build", return_value=mock_pipeline):
            return classify_sync("test query")

    @pytest.mark.parametrize("trajectory", _load_trajectories(), ids=[t["id"] for t in _load_trajectories()])
    def test_trajectory_route(self, trajectory: dict[str, Any]) -> None:
        result = self._run_classify_sync(trajectory["expected_intent"])
        assert result.intent == trajectory["expected_intent"], (
            f"{trajectory['id']}: expected intent {trajectory['expected_intent']!r}, "
            f"got {result.intent!r}"
        )
        assert result.route == trajectory["expected_route"], (
            f"{trajectory['id']}: expected route {trajectory['expected_route']!r}, "
            f"got {result.route!r}"
        )

    def test_rag_trajectories_have_rag_route(self) -> None:
        """Spot-check: all trajectories with expected_intent=product_search → rag route."""
        trajectories = _load_trajectories()
        rag_cases = [t for t in trajectories if t["expected_intent"] == "product_search"]
        for t in rag_cases:
            assert t["expected_route"] == "rag", f"{t['id']} should have rag route"

    def test_rejected_trajectories_are_out_of_scope(self) -> None:
        """All rejected trajectories must be out_of_scope intent."""
        trajectories = _load_trajectories()
        for t in trajectories:
            if t["expected_route"] == "rejected":
                assert t["expected_intent"] == "out_of_scope", (
                    f"{t['id']}: rejected route must have out_of_scope intent"
                )

    def test_agent_trajectories_have_specialist(self) -> None:
        """All agent-routed trajectories must declare an expected_specialist."""
        trajectories = _load_trajectories()
        for t in trajectories:
            if t["expected_route"] == "agent":
                assert t.get("expected_specialist") is not None, (
                    f"{t['id']}: agent trajectories must declare expected_specialist"
                )


class TestRouteConsistency:
    """Verify routing rules are internally consistent in classifier.py."""

    def test_out_of_scope_always_rejected(self) -> None:
        from app.ml.intent.classifier import _route_for_intent

        assert _route_for_intent("out_of_scope") == "rejected"

    def test_product_search_always_rag(self) -> None:
        from app.ml.intent.classifier import _route_for_intent

        assert _route_for_intent("product_search") == "rag"

    def test_complex_task_always_agent(self) -> None:
        from app.ml.intent.classifier import _route_for_intent

        assert _route_for_intent("complex_task") == "agent"

    @pytest.mark.parametrize("intent", [
        "order_status", "stock_check", "shipment_status", "invoice_query", "dunning_action"
    ])
    def test_all_direct_query_intents(self, intent: str) -> None:
        from app.ml.intent.classifier import _route_for_intent

        assert _route_for_intent(intent) == "direct_query"
