"""
Feature:  AI Chatbot — Intent Classifier (Tier 2)
Layer:    ML / Intent
Module:   app.ml.intent.tier2
Purpose:  DistilBERT fine-tuned on intent dataset, exported to ONNX Runtime
          for < 100ms inference. Handles cases where Tier 1 confidence < 0.70.
          Same 8 classes as Tier 1. If confidence < threshold OR model not
          present, escalates to Tier 3 (GPT-4o zero-shot).
          Model loaded from ml_models/intent_tier2/ (dir with model + tokenizer).
          If that directory does not exist, predict() returns None immediately
          (caller falls through to Tier 3).
Depends:  onnxruntime, transformers, numpy
HITL:     None — classification is internal.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

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

CONFIDENCE_THRESHOLD = 0.80  # below this → escalate to Tier 3
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml_models" / "intent_tier2"

_session: object | None = None  # onnxruntime.InferenceSession
_tokenizer: object | None = None  # AutoTokenizer
_label_map: dict[int, str] = {}
_loaded: bool = False
_unavailable: bool = False  # set True after one failed load attempt


@dataclass
class Tier2Result:
    intent: str
    confidence: float
    latency_ms: float
    escalate: bool


def _try_load() -> bool:
    """Attempt to load ONNX model + tokenizer. Returns True if successful."""
    global _session, _tokenizer, _label_map, _loaded, _unavailable

    if _unavailable:
        return False
    if _loaded:
        return True

    if not MODEL_DIR.exists():
        logger.info("intent_tier2_model_dir_not_found — skipping Tier 2")
        _unavailable = True
        return False

    try:
        import onnxruntime as ort  # noqa: PLC0415
        from transformers import AutoTokenizer  # noqa: PLC0415

        onnx_path = MODEL_DIR / "model.onnx"
        if not onnx_path.exists():
            logger.warning("intent_tier2_onnx_missing", extra={"path": str(onnx_path)})
            _unavailable = True
            return False

        _session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )
        _tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))  # type: ignore[no-untyped-call]

        # Load label map from saved file or build from class order
        label_map_path = MODEL_DIR / "label_map.json"
        if label_map_path.exists():
            import json  # noqa: PLC0415

            raw: dict[str, str] = json.loads(label_map_path.read_text(encoding="utf-8"))
            _label_map = {int(k): v for k, v in raw.items()}
        else:
            _label_map = {i: cls for i, cls in enumerate(INTENT_CLASSES)}

        _loaded = True
        logger.info("intent_tier2_loaded", extra={"dir": str(MODEL_DIR)})
        return True

    except Exception as exc:
        logger.warning("intent_tier2_load_error", extra={"error": str(exc)})
        _unavailable = True
        return False


def predict(text: str) -> Tier2Result | None:
    """
    Classify text using ONNX DistilBERT.
    Returns None if model is unavailable — caller routes to Tier 3.
    """
    if not _try_load():
        return None

    t0 = time.perf_counter()
    try:
        from transformers import PreTrainedTokenizerBase  # noqa: PLC0415

        tokenizer = _tokenizer
        assert isinstance(tokenizer, PreTrainedTokenizerBase)

        inputs = tokenizer(
            text,
            return_tensors="np",
            truncation=True,
            max_length=128,
            padding="max_length",
        )

        import onnxruntime as ort  # noqa: PLC0415

        session = _session
        assert isinstance(session, ort.InferenceSession)

        ort_inputs = {
            k: v for k, v in inputs.items() if k in [i.name for i in session.get_inputs()]
        }
        outputs = session.run(None, ort_inputs)
        logits: np.ndarray = outputs[0][0]

        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        proba = exp_logits / exp_logits.sum()
        idx = int(np.argmax(proba))
        confidence = float(proba[idx])
        intent = _label_map.get(idx, INTENT_CLASSES[idx % len(INTENT_CLASSES)])

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return Tier2Result(
            intent=intent,
            confidence=confidence,
            latency_ms=latency_ms,
            escalate=confidence < CONFIDENCE_THRESHOLD,
        )

    except Exception as exc:
        logger.warning("intent_tier2_predict_error", extra={"error": str(exc)})
        return None


def is_available() -> bool:
    """True if the ONNX model directory exists and loaded successfully."""
    return _try_load()
