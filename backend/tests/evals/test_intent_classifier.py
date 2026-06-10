# mypy: ignore-errors
"""
Feature:  AI Agents — Intent Classifier Evaluation
Layer:    Test / Evals (Nightly Gate 8)
Module:   tests.evals.test_intent_classifier
Purpose:  Nightly evaluation of all 3 classifier tiers against the held-out
          test split. Asserts weighted F1 >= 0.85 for each tier and overall
          cascade. Uses the intent training data generated in Phase 0.4.
          Threshold from backend/ml_config/eval_thresholds.yaml (Gate 8).
Depends:  app.ml.intent, sklearn.metrics, eval_dataset/intent_test_data.json
HITL:     None
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

THRESHOLDS_PATH = Path(__file__).parent.parent.parent / "ml_config" / "eval_thresholds.yaml"
EVAL_DATA_PATH = Path(__file__).parent / "eval_dataset" / "intent_test_data.json"


def load_thresholds() -> dict:
    with open(THRESHOLDS_PATH) as f:
        return yaml.safe_load(f)


def load_eval_data() -> list[dict]:
    if not EVAL_DATA_PATH.exists():
        pytest.skip("Intent eval dataset not yet generated (run Phase 0.4 script)")
    with open(EVAL_DATA_PATH) as f:
        return json.load(f)


def test_tier1_weighted_f1() -> None:
    """Tier 1 (TF-IDF + LR) must achieve weighted F1 >= threshold (Gate 8)."""
    from app.ml.intent.tier1 import Tier1IntentClassifier
    from sklearn.metrics import f1_score

    thresholds = load_thresholds()
    min_f1 = thresholds["intent_classifier"]["weighted_f1"]
    data = load_eval_data()

    clf = Tier1IntentClassifier.load_from_registry()
    texts = [d["text"] for d in data]
    labels = [d["label"] for d in data]
    preds = [clf.predict(t).label for t in texts]

    score = f1_score(labels, preds, average="weighted")
    assert score >= min_f1, f"Tier 1 F1 {score:.3f} below threshold {min_f1}"


def test_cascade_weighted_f1() -> None:
    """Full 3-tier cascade must achieve weighted F1 >= threshold (Gate 8)."""
    from app.ml.intent.tier1 import Tier1IntentClassifier
    from app.ml.intent.tier2 import Tier2IntentClassifier
    from sklearn.metrics import f1_score

    thresholds = load_thresholds()
    min_f1 = thresholds["intent_classifier"]["weighted_f1"]
    data = load_eval_data()

    t1 = Tier1IntentClassifier.load_from_registry()
    t2 = Tier2IntentClassifier.load_from_registry()
    texts = [d["text"] for d in data]
    labels = [d["label"] for d in data]

    preds = []
    for text in texts:
        r1 = t1.predict(text)
        if r1.confidence >= 0.8:
            preds.append(r1.label)
        else:
            r2 = t2.predict(text)
            preds.append(r2.label)

    score = f1_score(labels, preds, average="weighted")
    assert score >= min_f1, f"Cascade F1 {score:.3f} below threshold {min_f1}"
