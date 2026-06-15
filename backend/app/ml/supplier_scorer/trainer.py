"""
Feature:  Supplier Intelligence
Layer:    ML / Supplier Scorer
Module:   app.ml.supplier_scorer.trainer
Purpose:  Training script for the Ridge regression supplier scorer.
          Loads synthetic data from scripts/generate_supplier_data.py output.
          Pipeline: StandardScaler + Ridge(alpha=1.0, random_state=42).
          Logs to MLflow, registers as "supplier_scorer", saves pickle.
          Run with: uv run python -m app.ml.supplier_scorer.trainer
Depends:  scikit-learn, mlflow, joblib
HITL:     None — offline training.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import mlflow
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

DATASET_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "evals"
    / "eval_dataset"
    / "supplier_training_data.json"
)
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml_models"
MODEL_PATH = MODEL_DIR / "supplier_scorer.pkl"

FEATURE_ORDER = [
    "on_time_delivery_rate",
    "damage_rate",
    "avg_price_vs_market",
    "response_time_hours",
    "discrepancy_rate",
    "catalog_completeness",
]


def _load_dataset() -> tuple[np.ndarray, np.ndarray]:
    with open(DATASET_PATH) as f:
        examples: list[dict[str, object]] = json.load(f)

    feat_rows = []
    label_rows = []
    for ex in examples:
        feat_rows.append([float(str(ex[k])) for k in FEATURE_ORDER])
        label_rows.append(float(str(ex["score"])))

    return np.array(feat_rows, dtype=float), np.array(label_rows, dtype=float)


def train() -> None:
    features, labels = _load_dataset()
    logger.info("Loaded %d training examples", len(features))

    scaler = StandardScaler()
    feat_scaled = scaler.fit_transform(features)

    ridge = Ridge(alpha=1.0, random_state=42)

    # 5-fold CV
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2 = cross_val_score(ridge, feat_scaled, labels, cv=cv, scoring="r2")
    cv_mae = cross_val_score(ridge, feat_scaled, labels, cv=cv, scoring="neg_mean_absolute_error")
    logger.info("CV R² = %.4f ± %.4f", cv_r2.mean(), cv_r2.std())
    logger.info("CV MAE = %.4f ± %.4f", -cv_mae.mean(), cv_mae.std())

    ridge.fit(feat_scaled, labels)

    y_pred = ridge.predict(feat_scaled)
    train_r2 = float(r2_score(labels, y_pred))
    train_mae = float(mean_absolute_error(labels, y_pred))
    logger.info("Train R² = %.4f, MAE = %.4f", train_r2, train_mae)

    bundle = {"scaler": scaler, "ridge": ridge, "feature_order": FEATURE_ORDER}

    mlflow.set_tracking_uri("http://localhost:5000")
    with mlflow.start_run(run_name="supplier_scorer"):
        mlflow.log_param("model", "Ridge")
        mlflow.log_param("alpha", 1.0)
        mlflow.log_param("random_state", 42)
        mlflow.log_metric("cv_r2_mean", float(cv_r2.mean()))
        mlflow.log_metric("cv_mae_mean", float(-cv_mae.mean()))
        mlflow.log_metric("train_r2", train_r2)
        mlflow.log_metric("train_mae", train_mae)
        mlflow.sklearn.log_model(ridge, "supplier_scorer")
        active = mlflow.active_run()
        if active is not None:
            mlflow.register_model(
                f"runs:/{active.info.run_id}/supplier_scorer",
                "supplier_scorer",
            )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
