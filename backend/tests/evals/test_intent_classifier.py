# mypy: ignore-errors
"""
Feature:  AI Agents — Intent Classifier Evaluation
Layer:    Test / Evals (Nightly Gate 8)
Module:   tests.evals.test_intent_classifier
Purpose:  Nightly evaluation of the intent classifier against the held-out test
          split (intent_test_set.json from Phase 0.4). Asserts weighted F1 >=
          threshold (ml_config/eval_thresholds.yaml → intent_classifier.weighted_f1).
          Tier 1 cold-trains in-memory from the committed training data, so this
          runs in CI with no model artifact and no network. The cascade test
          additionally uses Tier 2 when its ONNX model is present, otherwise it
          falls back to the Tier 1 prediction (never calls Tier 3 / network).
Depends:  app.ml.intent.tier1, app.ml.intent.tier2, sklearn.metrics
HITL:     None
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

THRESHOLDS_PATH = Path(__file__).parent.parent.parent / "ml_config" / "eval_thresholds.yaml"
EVAL_DATA_PATH = Path(__file__).parent / "eval_dataset" / "intent_test_set.json"


def load_thresholds() -> dict:
    with open(THRESHOLDS_PATH) as f:
        return yaml.safe_load(f)


def load_eval_data() -> list[dict]:
    if not EVAL_DATA_PATH.exists():
        pytest.skip("Intent eval dataset not yet generated (run Phase 0.4 script)")
    with open(EVAL_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_tier1_weighted_f1() -> None:
    """Tier 1 (TF-IDF + LR) must achieve weighted F1 >= threshold (Gate 8)."""
    from app.ml.intent import tier1
    from sklearn.metrics import f1_score

    thresholds = load_thresholds()
    min_f1 = thresholds["intent_classifier"]["weighted_f1"]
    data = load_eval_data()

    texts = [d["text"] for d in data]
    labels = [d["intent"] for d in data]
    preds = [tier1.predict(t).intent for t in texts]

    score = f1_score(labels, preds, average="weighted")
    assert score >= min_f1, f"Tier 1 weighted F1 {score:.3f} below threshold {min_f1}"


def test_cascade_weighted_f1() -> None:
    """Full cascade (Tier1 → Tier2 when available) must achieve weighted F1 >= threshold."""
    from app.ml.intent import tier1, tier2
    from sklearn.metrics import f1_score

    thresholds = load_thresholds()
    min_f1 = thresholds["intent_classifier"]["weighted_f1"]
    data = load_eval_data()

    texts = [d["text"] for d in data]
    labels = [d["intent"] for d in data]

    preds: list[str] = []
    for text in texts:
        r1 = tier1.predict(text)
        if not r1.escalate:
            preds.append(r1.intent)
            continue
        # Tier 2 is optional (ONNX model may be absent in CI) — fall back to Tier 1.
        r2 = tier2.predict(text)
        preds.append(r2.intent if r2 is not None else r1.intent)

    score = f1_score(labels, preds, average="weighted")
    assert score >= min_f1, f"Cascade weighted F1 {score:.3f} below threshold {min_f1}"
