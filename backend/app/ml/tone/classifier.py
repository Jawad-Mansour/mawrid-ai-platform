"""
Feature:  Dunning Engine — Tone Classifier
Layer:    ML / Tone
Module:   app.ml.tone.classifier
Purpose:  3-class tone classification (gentle / neutral / firm) for dunning
          messages. Priority-ordered rules applied first (same as training
          labels); ML model (GBC, SMOTE, random_state=42) used as fallback
          for cases no rule covers. Loaded at startup via _get_model();
          returns None if model not yet trained (neutral fallback).
          Inference < 1ms via numpy feature array.
Depends:  scikit-learn, joblib, app.core.dunning.models
HITL:     None — classification is internal.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from app.core.dunning.models import ToneClass, ToneClassifierResult

logger = logging.getLogger(__name__)

_SEGMENT_MAP: dict[str, int] = {
    "VIP": 0,
    "Regular": 1,
    "At-Risk": 2,
    "Dormant": 3,
}
_LABEL_REVERSE: dict[int, ToneClass] = {
    0: ToneClass.GENTLE,
    1: ToneClass.NEUTRAL,
    2: ToneClass.FIRM,
}

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "ml_models" / "tone_classifier.pkl"

# Lazy-loaded bundle: {"scaler": ..., "clf": ..., "label_map": ..., "segment_map": ...}
_bundle: dict[str, Any] | None = None
_load_attempted = False


def _get_model() -> dict[str, Any] | None:
    global _bundle, _load_attempted
    if _load_attempted:
        return _bundle
    _load_attempted = True
    if not MODEL_PATH.exists():
        logger.warning("tone_classifier_model_not_found: %s", MODEL_PATH)
        return None
    try:
        import joblib  # noqa: PLC0415

        _bundle = joblib.load(MODEL_PATH)
        logger.info("tone_classifier_loaded: %s", MODEL_PATH)
    except Exception as exc:
        logger.error("tone_classifier_load_failed: %s", exc)
        _bundle = None
    return _bundle


def _apply_priority_rules(
    days_overdue: int,
    customer_segment: str,
    payment_history_score: float,
    previous_dunning_count: int,
) -> ToneClass | None:
    """
    Priority-ordered rules — first match wins. Returns None if no rule fires.
    Must match generate_tone_data.py's determine_tone() exactly.
    """
    if days_overdue <= 7:
        return ToneClass.GENTLE
    if customer_segment == "VIP":
        return ToneClass.GENTLE
    if (
        customer_segment in ("At-Risk", "Dormant")
        and days_overdue >= 14
        and previous_dunning_count >= 2
    ):
        return ToneClass.FIRM
    if payment_history_score >= 0.8:
        return ToneClass.GENTLE
    return None  # no rule fired — ML handles it


def classify(
    days_overdue: int,
    customer_segment: str,
    overdue_amount: float,
    payment_history_score: float,
    previous_dunning_count: int,
) -> ToneClassifierResult:
    """
    Classify the tone for a dunning message.

    Priority rules applied first (deterministic, < 1µs).
    ML model used as fallback; if model not loaded → neutral.
    """
    features = {
        "days_overdue": float(days_overdue),
        "customer_segment_encoded": float(_SEGMENT_MAP.get(customer_segment, 1)),
        "overdue_amount": overdue_amount,
        "payment_history_score": payment_history_score,
        "previous_dunning_count": float(previous_dunning_count),
    }

    # ── Priority rules (always applied first) ────────────────────────────────
    rule_result = _apply_priority_rules(
        days_overdue, customer_segment, payment_history_score, previous_dunning_count
    )
    if rule_result is not None:
        return ToneClassifierResult(tone=rule_result, confidence=1.0, features=features)

    # ── ML fallback ───────────────────────────────────────────────────────────
    bundle = _get_model()
    if bundle is None:
        return ToneClassifierResult(tone=ToneClass.NEUTRAL, confidence=0.5, features=features)

    try:
        scaler = bundle["scaler"]
        clf = bundle["clf"]
        feat = np.array(
            [
                [
                    float(days_overdue),
                    float(_SEGMENT_MAP.get(customer_segment, 1)),
                    overdue_amount,
                    payment_history_score,
                    float(previous_dunning_count),
                ]
            ]
        )
        feat_scaled = scaler.transform(feat)
        label_int: int = int(clf.predict(feat_scaled)[0])
        proba: np.ndarray = clf.predict_proba(feat_scaled)[0]
        confidence = float(proba.max())
        tone = _LABEL_REVERSE.get(label_int, ToneClass.NEUTRAL)
        return ToneClassifierResult(tone=tone, confidence=confidence, features=features)
    except Exception as exc:
        logger.error("tone_classifier_inference_failed: %s", exc)
        return ToneClassifierResult(tone=ToneClass.NEUTRAL, confidence=0.0, features=features)
