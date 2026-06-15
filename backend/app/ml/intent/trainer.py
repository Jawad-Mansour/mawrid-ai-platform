"""
Feature:  AI Chatbot — Intent Classifier Training
Layer:    ML / Scripts
Module:   app.ml.intent.trainer
Purpose:  Training script for Tier 1 (TF-IDF+LR) and Tier 2 (DistilBERT fine-tune
          → ONNX export). Consumes intent dataset from
          backend/tests/evals/eval_dataset/intent_training_data.json.
          Tier 1: fast, always trained. Registered in MLflow as "intent_tier1".
          Tier 2: fine-tunes distilbert-base-multilingual-cased, exports ONNX.
          Run: uv run python -m app.ml.intent.trainer [--tier {1,2,all}]
          Tier 2 training requires ~30-60 min on CPU; skip with --tier 1 for speed.
Depends:  scikit-learn, transformers, optimum, onnxruntime, mlflow, joblib
HITL:     None.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

DATA_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "evals"
    / "eval_dataset"
    / "intent_training_data.json"
)
TEST_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "evals"
    / "eval_dataset"
    / "intent_test_set.json"
)
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml_models"
TIER1_PATH = MODEL_DIR / "intent_tier1.pkl"
TIER2_DIR = MODEL_DIR / "intent_tier2"

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


def _load_dataset(path: Path) -> tuple[list[str], list[str]]:
    examples: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    texts = [e["text"] for e in examples]
    labels = [e["intent"] for e in examples]
    return texts, labels


def train_tier1() -> float:
    """Train TF-IDF + LR, save pkl, register in MLflow. Returns test F1."""
    import joblib  # noqa: PLC0415
    import mlflow  # noqa: PLC0415
    import mlflow.sklearn  # noqa: PLC0415
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    from sklearn.metrics import f1_score  # noqa: PLC0415
    from sklearn.model_selection import cross_val_score  # noqa: PLC0415
    from sklearn.pipeline import Pipeline  # noqa: PLC0415

    logger.info("Loading training data from %s", DATA_PATH)
    train_texts, train_labels = _load_dataset(DATA_PATH)

    pipeline = Pipeline(
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

    # 5-fold cross-validation
    cv_f1 = cross_val_score(pipeline, train_texts, train_labels, cv=5, scoring="f1_macro")
    logger.info("Tier 1 CV F1 macro: %.4f ± %.4f", cv_f1.mean(), cv_f1.std())

    # Fit on full training set
    pipeline.fit(train_texts, train_labels)

    # Test set evaluation
    test_f1 = 0.0
    if TEST_PATH.exists():
        test_texts, test_labels = _load_dataset(TEST_PATH)
        preds = pipeline.predict(test_texts)
        test_f1 = float(f1_score(test_labels, preds, average="macro"))
        logger.info("Tier 1 test F1 macro: %.4f", test_f1)

    # Always save pkl first — MLflow is optional (requires Docker)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, TIER1_PATH)
    logger.info("Tier 1 saved to %s", TIER1_PATH)

    # MLflow logging (best-effort — skipped if server unavailable)
    try:
        mlflow.set_tracking_uri("http://localhost:5000")
        with mlflow.start_run(run_name="intent_tier1"):
            mlflow.log_param("model", "TF-IDF+LR")
            mlflow.log_param("C", 5.0)
            mlflow.log_param("ngram_range", "(1,2)")
            mlflow.log_param("max_features", 30000)
            mlflow.log_metric("cv_f1_macro_mean", float(cv_f1.mean()))
            mlflow.log_metric("cv_f1_macro_std", float(cv_f1.std()))
            if test_f1:
                mlflow.log_metric("test_f1_macro", test_f1)
            mlflow.sklearn.log_model(pipeline, "intent_tier1")
            active = mlflow.active_run()
            if active is not None:
                mlflow.register_model(
                    f"runs:/{active.info.run_id}/intent_tier1",
                    "intent_tier1",
                )
    except Exception as exc:
        logger.warning("mlflow_logging_skipped (server unavailable): %s", exc)

    return test_f1


def train_tier2() -> None:
    """
    Fine-tune distilbert-base-multilingual-cased on intent dataset.
    Export to ONNX for < 100ms inference.
    Requires transformers, optimum[onnxruntime].
    Estimated runtime: 30-60 min on CPU.
    """
    import torch  # noqa: PLC0415
    from torch.utils.data import Dataset  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    logger.info("Loading dataset for Tier 2 fine-tuning")
    train_texts, train_labels = _load_dataset(DATA_PATH)

    label2id = {cls: i for i, cls in enumerate(INTENT_CLASSES)}
    id2label = {i: cls for i, cls in enumerate(INTENT_CLASSES)}
    num_labels = len(INTENT_CLASSES)

    base_model = "distilbert-base-multilingual-cased"
    tokenizer = AutoTokenizer.from_pretrained(base_model)  # type: ignore[no-untyped-call]
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
    )

    class IntentDataset(Dataset[dict[str, torch.Tensor]]):
        def __init__(self, texts: list[str], labels: list[str]) -> None:
            self.encodings = tokenizer(
                texts,
                truncation=True,
                max_length=128,
                padding="max_length",
                return_tensors="pt",
            )
            self.labels_idx = [label2id[lbl] for lbl in labels]

        def __len__(self) -> int:
            return len(self.labels_idx)

        def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
            item = {k: v[idx] for k, v in self.encodings.items()}
            item["labels"] = torch.tensor(self.labels_idx[idx])
            return item

    train_dataset = IntentDataset(train_texts, train_labels)

    training_args = TrainingArguments(
        output_dir=str(TIER2_DIR / "_checkpoints"),
        num_train_epochs=3,
        per_device_train_batch_size=16,
        warmup_steps=50,
        weight_decay=0.01,
        logging_dir=str(TIER2_DIR / "_logs"),
        logging_steps=50,
        save_strategy="no",
        report_to=[],  # suppress wandb/tensorboard
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
    )

    logger.info("Starting DistilBERT fine-tuning (this takes 30-60 min on CPU)")
    trainer.train()

    # Save tokenizer + model for ONNX export
    tmp_dir = TIER2_DIR / "_pytorch"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(tmp_dir))
    tokenizer.save_pretrained(str(tmp_dir))

    # Export to ONNX using optimum
    logger.info("Exporting to ONNX")
    from optimum.onnxruntime import ORTModelForSequenceClassification  # noqa: PLC0415

    TIER2_DIR.mkdir(parents=True, exist_ok=True)
    ort_model = ORTModelForSequenceClassification.from_pretrained(str(tmp_dir), export=True)
    ort_model.save_pretrained(str(TIER2_DIR))
    tokenizer.save_pretrained(str(TIER2_DIR))

    # Save label map
    import json as _json  # noqa: PLC0415

    (TIER2_DIR / "label_map.json").write_text(
        _json.dumps({str(i): cls for i, cls in id2label.items()}, indent=2),
        encoding="utf-8",
    )
    logger.info("Tier 2 ONNX model saved to %s", TIER2_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train intent classifier")
    parser.add_argument("--tier", choices=["1", "2", "all"], default="1")
    args = parser.parse_args()

    if args.tier in ("1", "all"):
        f1 = train_tier1()
        if f1 < 0.85:
            logger.warning("WARNING: Tier 1 F1 %.4f is below the 0.85 CI gate threshold", f1)
        else:
            logger.info("Tier 1 meets CI gate: F1=%.4f >= 0.85", f1)

    if args.tier in ("2", "all"):
        train_tier2()
