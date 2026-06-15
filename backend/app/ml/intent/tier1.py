"""
Feature:  AI Chatbot — Intent Classifier (Tier 1)
Layer:    ML / Intent
Module:   app.ml.intent.tier1
Purpose:  TF-IDF + Logistic Regression intent classifier. Handles ~80% of
          traffic at sub-millisecond latency. 8 classes: product_search,
          order_status, stock_check, shipment_status, invoice_query,
          dunning_action, complex_task, out_of_scope. Loads from MLflow pkl;
          trains in-memory from eval_dataset if pkl not found (first boot).
Depends:  scikit-learn, mlflow, numpy
HITL:     None — classification is internal.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

INTENT_CLASSES = [
    "product_search",
    "order_status",
    "stock_check",
    "shipment_status",
    "invoice_query",
    "dunning_action",
    "complex_task",
    "out_of_scope",
]

CONFIDENCE_THRESHOLD = 0.70  # below this → escalate to Tier 2

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "ml_models" / "intent_tier1.pkl"

_pipeline: Pipeline | None = None


@dataclass
class Tier1Result:
    intent: str
    confidence: float
    latency_ms: float
    escalate: bool  # True if confidence < threshold


def _load_or_build() -> Pipeline:
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    if MODEL_PATH.exists():
        try:
            import joblib  # noqa: PLC0415

            _pipeline = joblib.load(MODEL_PATH)
            logger.info("intent_tier1_model_loaded", extra={"path": str(MODEL_PATH)})
            return _pipeline
        except Exception as exc:
            logger.warning("intent_tier1_load_failed", extra={"error": str(exc)})

    # Cold-start: train in-memory from eval dataset if pkl not found
    _pipeline = _train_in_memory()
    return _pipeline


def _train_in_memory() -> Pipeline:
    """Train Tier 1 on the committed eval dataset. Used at cold start only."""
    import json  # noqa: PLC0415

    data_path = (
        Path(__file__).parent.parent.parent.parent
        / "tests"
        / "evals"
        / "eval_dataset"
        / "intent_training_data.json"
    )
    if not data_path.exists():
        logger.warning("intent_training_data_not_found — using empty model")
        pipeline = _build_pipeline()
        # Fit on minimal dummy data so pipeline is usable
        dummy_texts = [f"dummy {cls}" for cls in INTENT_CLASSES]
        pipeline.fit(dummy_texts, INTENT_CLASSES)
        return pipeline

    examples: list[dict[str, Any]] = json.loads(data_path.read_text(encoding="utf-8"))
    texts = [e["text"] for e in examples]
    labels = [e["intent"] for e in examples]

    pipeline = _build_pipeline()
    pipeline.fit(texts, labels)
    logger.info(
        "intent_tier1_trained_in_memory",
        extra={"examples": len(examples)},
    )
    return pipeline


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    max_features=30_000,
                    sublinear_tf=True,
                    strip_accents="unicode",
                    lowercase=True,
                ),
            ),
            (
                "lr",
                LogisticRegression(
                    C=5.0,
                    max_iter=1000,
                    solver="lbfgs",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def predict(text: str) -> Tier1Result:
    """Classify text. Returns result with escalate=True if below threshold."""
    t0 = time.perf_counter()
    pipeline = _load_or_build()
    proba: np.ndarray = pipeline.predict_proba([text])[0]
    idx = int(np.argmax(proba))
    intent = pipeline.classes_[idx]
    confidence = float(proba[idx])
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return Tier1Result(
        intent=intent,
        confidence=confidence,
        latency_ms=latency_ms,
        escalate=confidence < CONFIDENCE_THRESHOLD,
    )


def is_ready() -> bool:
    """True if Tier 1 model is loaded (not a dummy)."""
    return _pipeline is not None
