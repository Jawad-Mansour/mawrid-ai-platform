"""
Feature:  RAG Pipeline — Quality Evaluation
Layer:    Test / Evals (Nightly)
Module:   tests.evals.test_rag_quality
Purpose:  RAGAS-based nightly evaluation of the 6-technique RAG pipeline.
          Uses a real LLM (GPT-4o) and real pgvector DB with seeded product data.
          Thresholds from backend/ml_config/eval_thresholds.yaml (ragas section).
          Fails if any metric falls below threshold — this is Gate 7 in CI.
          Run: uv run pytest backend/tests/evals/test_rag_quality.py
          Requires: docker compose up + alembic upgrade head + vault seeded
Depends:  ragas>=0.2.6, app.rag, real LLM, real DB
HITL:     None
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

THRESHOLDS_PATH = Path(__file__).parent.parent.parent / "ml_config" / "eval_thresholds.yaml"


def load_thresholds() -> dict[str, Any]:
    with open(THRESHOLDS_PATH) as f:
        return cast(dict[str, Any], yaml.safe_load(f))


@pytest.mark.asyncio
async def test_rag_faithfulness_above_threshold() -> None:
    """RAG pipeline faithfulness must meet nightly threshold (Gate 7)."""
    pytest.importorskip("ragas")
    thresholds = load_thresholds()
    min_faithfulness: float = thresholds["ragas"]["faithfulness"]

    from tests.evals.helpers.rag_evaluator import evaluate_rag_faithfulness

    score = await evaluate_rag_faithfulness()
    assert score >= min_faithfulness, (
        f"RAG faithfulness {score:.3f} below threshold {min_faithfulness}"
    )


@pytest.mark.asyncio
async def test_rag_answer_relevance_above_threshold() -> None:
    """RAG pipeline answer relevancy must meet nightly threshold (Gate 7)."""
    pytest.importorskip("ragas")
    thresholds = load_thresholds()
    min_relevance: float = thresholds["ragas"]["answer_relevancy"]

    from tests.evals.helpers.rag_evaluator import evaluate_rag_answer_relevance

    score = await evaluate_rag_answer_relevance()
    assert score >= min_relevance, (
        f"RAG answer relevancy {score:.3f} below threshold {min_relevance}"
    )


@pytest.mark.asyncio
async def test_rag_context_precision_above_threshold() -> None:
    """RAG pipeline context precision must meet nightly threshold (Gate 7)."""
    pytest.importorskip("ragas")
    thresholds = load_thresholds()
    min_precision: float = thresholds["ragas"]["context_precision"]

    from tests.evals.helpers.rag_evaluator import evaluate_rag_context_precision

    score = await evaluate_rag_context_precision()
    assert score >= min_precision, (
        f"RAG context precision {score:.3f} below threshold {min_precision}"
    )
