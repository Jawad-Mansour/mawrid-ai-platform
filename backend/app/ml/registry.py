"""
Feature:  MLOps Governance
Layer:    ML / Registry
Module:   app.ml.registry
Purpose:  Champion/challenger gating before MLflow production promotion.
          SHA-256 artifact verification on every model load from disk.
          Downgrade path: archived model can be promoted back without retraining
          by calling promote_model() with the archived version number.
Depends:  mlflow, hashlib, pathlib
HITL:     None — governance is automated.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class ModelRecord:
    name: str
    version: str
    stage: str            # "staging" | "production" | "archived"
    sha256_hash: str      # empty string if not tagged
    metrics: dict[str, float] = field(default_factory=dict)


# ── SHA-256 artifact verification ─────────────────────────────────────────────


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file in 64 KiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected_hash: str) -> bool:
    """
    Return True if the file's SHA-256 matches expected_hash.
    Logs an error with truncated hashes on mismatch so it is easy to diagnose.
    """
    if not path.exists():
        logger.warning("sha256_verify_file_not_found: %s", path)
        return False
    actual = compute_sha256(path)
    if actual != expected_hash:
        logger.error(
            "sha256_mismatch: path=%s expected=%s… actual=%s…",
            path,
            expected_hash[:12],
            actual[:12],
        )
        return False
    return True


# ── Champion / challenger gate ────────────────────────────────────────────────


def champion_challenger_gate(
    new_metrics: dict[str, float],
    champion_metrics: dict[str, float],
    metric_key: str,
    higher_is_better: bool = True,
) -> bool:
    """
    Return True if the challenger matches or beats the champion on metric_key.

    A tolerance of 0.001 is applied so that trivially equivalent models are not
    blocked.  If either model is missing the metric, the gate rejects the
    challenger (fail-safe).

    higher_is_better=True  → F1, accuracy, precision, recall
    higher_is_better=False → MAE, MSE, RMSE
    """
    new_val = new_metrics.get(metric_key)
    champ_val = champion_metrics.get(metric_key)

    if new_val is None or champ_val is None:
        logger.warning(
            "champion_challenger_gate: metric '%s' missing — challenger rejected",
            metric_key,
        )
        return False

    passes = (
        new_val >= champ_val - 0.001
        if higher_is_better
        else new_val <= champ_val + 0.001
    )
    logger.info(
        "champion_challenger_gate: metric=%s new=%.4f champion=%.4f higher_is_better=%s passes=%s",
        metric_key,
        new_val,
        champ_val,
        higher_is_better,
        passes,
    )
    return passes


# ── MLflow registry helpers ───────────────────────────────────────────────────


def get_mlflow_production_model(
    name: str,
    tracking_uri: str = "http://localhost:5000",
) -> ModelRecord | None:
    """
    Fetch the Production stage model record from the MLflow model registry.
    Returns None if MLflow is unreachable or the model has no Production version.
    Never raises — intended to be called at startup where partial failure is OK.
    """
    try:
        import mlflow  # noqa: PLC0415
        from mlflow.tracking import MlflowClient  # noqa: PLC0415

        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient()
        versions = client.get_latest_versions(name, stages=["Production"])
        if not versions:
            return None
        v = versions[0]
        metrics: dict[str, float] = {}
        if v.run_id:
            run = client.get_run(v.run_id)
            metrics = {k: float(val) for k, val in run.data.metrics.items()}
        return ModelRecord(
            name=name,
            version=v.version,
            stage="production",
            sha256_hash=v.tags.get("sha256", ""),
            metrics=metrics,
        )
    except Exception as exc:
        logger.warning("get_mlflow_production_model_failed: name=%s error=%s", name, exc)
        return None


def promote_model(
    name: str,
    version: str,
    new_metrics: dict[str, float],
    metric_key: str,
    tracking_uri: str = "http://localhost:5000",
    higher_is_better: bool = True,
) -> bool:
    """
    Promote a challenger model version to Production if it passes the gate.

    Steps:
    1. Fetch current Production version (champion).
    2. Run champion/challenger gate.
    3. Archive the champion.
    4. Promote the challenger to Production.

    Returns True if the promotion succeeded, False if the gate rejected or
    MLflow was unreachable.
    """
    champion = get_mlflow_production_model(name, tracking_uri)
    if champion is not None:
        if not champion_challenger_gate(
            new_metrics, champion.metrics, metric_key, higher_is_better
        ):
            logger.warning("promote_model: challenger rejected for '%s'", name)
            return False

    try:
        import mlflow  # noqa: PLC0415
        from mlflow.tracking import MlflowClient  # noqa: PLC0415

        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient()

        if champion is not None:
            client.transition_model_version_stage(name, champion.version, "Archived")

        client.transition_model_version_stage(name, version, "Production")
        logger.info(
            "promote_model: '%s' version %s promoted to Production", name, version
        )
        return True
    except Exception as exc:
        logger.error("promote_model_failed: name=%s error=%s", name, exc)
        return False
