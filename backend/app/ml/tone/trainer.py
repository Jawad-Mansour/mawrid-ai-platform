"""
Feature:  Dunning Engine — Tone Classifier
Layer:    ML / Tone
Module:   app.ml.tone.trainer
Purpose:  Training script for the 3-class tone classifier (gentle/neutral/firm).
          Loads labeled data from scripts/generate_tone_data.py output (3000
          examples, 1000 per class). Feature pipeline: ordinal encoding for
          customer_segment + StandardScaler + GradientBoostingClassifier
          (random_state=42). SMOTE applied before training for robustness.
          Logs params + metrics to MLflow, registers model as "tone_classifier".
          Saves pickle to backend/ml_models/tone_classifier.pkl as local fallback.
          Run with: uv run python -m app.ml.tone.trainer
Depends:  scikit-learn, imbalanced-learn, mlflow, joblib
HITL:     None — training is offline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import mlflow
import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Segment ordinal encoding — order reflects "risk level" for classifier
_SEGMENT_MAP: dict[str, int] = {
    "VIP": 0,
    "Regular": 1,
    "At-Risk": 2,
    "Dormant": 3,
}
_LABEL_MAP: dict[str, int] = {"gentle": 0, "neutral": 1, "firm": 2}
_LABEL_REVERSE: dict[int, str] = {v: k for k, v in _LABEL_MAP.items()}

DATASET_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "evals"
    / "eval_dataset"
    / "tone_training_data.json"
)
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml_models"
MODEL_PATH = MODEL_DIR / "tone_classifier.pkl"


def _load_dataset() -> tuple[np.ndarray, np.ndarray]:
    with open(DATASET_PATH) as f:
        examples: list[dict[str, object]] = json.load(f)

    feat_rows = []
    label_rows = []
    for ex in examples:
        segment_int = _SEGMENT_MAP.get(str(ex["customer_segment"]), 1)
        feat_rows.append(
            [
                float(str(ex["days_overdue"])),
                float(segment_int),
                float(str(ex["overdue_amount"])),
                float(str(ex["payment_history_score"])),
                float(str(ex["previous_dunning_count"])),
            ]
        )
        label_rows.append(_LABEL_MAP[str(ex["tone"])])

    return np.array(feat_rows, dtype=float), np.array(label_rows, dtype=int)


def train() -> None:
    features, labels = _load_dataset()
    logger.info("Loaded %d training examples", len(features))

    # SMOTE — robust oversampling even though data is already balanced
    smote = SMOTE(random_state=42)
    feat_res, labels_res = smote.fit_resample(features, labels)
    logger.info("After SMOTE: %d examples", len(feat_res))

    scaler = StandardScaler()
    feat_scaled = scaler.fit_transform(feat_res)

    clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=10,
        random_state=42,
    )

    # Cross-validation before final fit
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(clf, feat_scaled, labels_res, cv=cv, scoring="f1_weighted")
    logger.info("CV F1 (weighted) = %.4f +/- %.4f", cv_scores.mean(), cv_scores.std())

    # Final fit on full (SMOTE'd) dataset
    clf.fit(feat_scaled, labels_res)

    # Training report
    y_pred = clf.predict(feat_scaled)
    train_f1 = f1_score(labels_res, y_pred, average="weighted")
    report = classification_report(labels_res, y_pred, target_names=["gentle", "neutral", "firm"])
    logger.info("Training F1 (weighted) = %.4f", train_f1)
    logger.info("\n%s", report)

    # Bundle scaler + classifier together so inference doesn't need to re-create scaler
    bundle = {"scaler": scaler, "clf": clf, "label_map": _LABEL_MAP, "segment_map": _SEGMENT_MAP}

    # MLflow logging
    mlflow.set_tracking_uri("http://localhost:5000")
    with mlflow.start_run(run_name="tone_classifier") as run:
        mlflow.log_param("model", "GradientBoostingClassifier")
        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 4)
        mlflow.log_param("random_state", 42)
        mlflow.log_param("smote", True)
        mlflow.log_metric("cv_f1_weighted_mean", float(cv_scores.mean()))
        mlflow.log_metric("cv_f1_weighted_std", float(cv_scores.std()))
        mlflow.log_metric("train_f1_weighted", float(train_f1))
        mlflow.sklearn.log_model(clf, "tone_clf")
        mlflow.register_model(f"runs:/{run.info.run_id}/tone_clf", "tone_classifier")

    # Local pickle fallback
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
