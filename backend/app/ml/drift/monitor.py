"""
Feature:  Model Health & Drift Detection (cross-cutting)
Layer:    ML / Drift
Module:   app.ml.drift.monitor
Purpose:  Population Stability Index (PSI) for numeric feature distributions,
          chi-square test for categorical label distribution shift, and cosine
          distance for embedding centroid drift.  All functions are pure
          (numpy/scipy only) so they can be unit-tested without any DB or LLM.
          run_drift_report() aggregates a list of DriftResult into a single
          DriftReport with an overall_status string used by GET /admin/ai-health
          and nightly CI Gate 9.
Depends:  numpy, scipy, yaml
HITL:     None — drift is automated monitoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy import stats

logger = logging.getLogger(__name__)

_THRESHOLDS_PATH = (
    Path(__file__).parent.parent.parent.parent / "ml_config" / "drift_thresholds.yaml"
)


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class DriftResult:
    model_name: str
    metric_type: str          # "psi" | "chi_square" | "cosine"
    metric_value: float
    status: str               # "ok" | "warning" | "severe"
    details: str = ""


@dataclass
class DriftReport:
    results: list[DriftResult] = field(default_factory=list)
    overall_status: str = "ok"   # "ok" | "warning" | "severe"
    checked_models: list[str] = field(default_factory=list)


# ── Core metric functions (pure, no side effects) ──────────────────────────────


def compute_psi(
    baseline: np.ndarray,
    current: np.ndarray,
    bins: int = 10,
) -> float:
    """
    Population Stability Index between two 1-D numeric distributions.

    PSI < 0.10 → stable
    PSI 0.10–0.20 → moderate shift (warning)
    PSI > 0.20 → significant shift (severe)
    """
    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    min_val = float(min(baseline.min(), current.min()))
    max_val = float(max(baseline.max(), current.max()))
    if min_val == max_val:
        return 0.0

    breakpoints = np.linspace(min_val, max_val, bins + 1)
    baseline_counts, _ = np.histogram(baseline, bins=breakpoints)
    current_counts, _ = np.histogram(current, bins=breakpoints)

    eps = 1e-8
    baseline_pct = np.maximum(baseline_counts / len(baseline), eps)
    current_pct = np.maximum(current_counts / len(current), eps)

    psi = float(np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct)))
    return abs(psi)


def compute_chi_square(
    baseline_counts: dict[str, int],
    current_counts: dict[str, int],
) -> tuple[float, float]:
    """
    Chi-square test for categorical distribution shift.

    Returns (statistic, p_value).  p < 0.05 → warning;  p < 0.01 → severe.
    All keys from baseline are used; keys missing in current count as 0.
    """
    keys = sorted(baseline_counts.keys())
    if not keys:
        return 0.0, 1.0

    baseline_arr = np.array([baseline_counts.get(k, 0) for k in keys], dtype=float)
    current_arr = np.array([current_counts.get(k, 0) for k in keys], dtype=float)

    if baseline_arr.sum() == 0 or current_arr.sum() == 0:
        return 0.0, 1.0

    # Scale expected to match observed total
    expected = baseline_arr / baseline_arr.sum() * current_arr.sum()
    expected = np.maximum(expected, 1e-8)

    result = stats.chisquare(f_obs=current_arr, f_exp=expected)
    return float(result.statistic), float(result.pvalue)


def compute_cosine_drift(
    baseline_centroid: np.ndarray,
    current_centroid: np.ndarray,
) -> float:
    """
    Cosine distance between two embedding centroids (0 = identical, 2 = opposite).
    Values > 0.20 indicate significant embedding space drift.
    """
    norm_b = float(np.linalg.norm(baseline_centroid))
    norm_c = float(np.linalg.norm(current_centroid))
    if norm_b < 1e-10 or norm_c < 1e-10:
        return 0.0
    cosine_similarity = float(
        np.dot(baseline_centroid, current_centroid) / (norm_b * norm_c)
    )
    return 1.0 - cosine_similarity


# ── Threshold helpers ─────────────────────────────────────────────────────────


def _load_thresholds() -> dict[str, Any]:
    try:
        raw: dict[str, Any] = yaml.safe_load(_THRESHOLDS_PATH.read_text()) or {}
        return raw
    except Exception:
        return {}


def _psi_status(psi: float, model_thresholds: dict[str, Any]) -> str:
    severe = float(model_thresholds.get("psi_severe", 0.20))
    warning = float(model_thresholds.get("psi_warning", 0.10))
    if psi >= severe:
        return "severe"
    if psi >= warning:
        return "warning"
    return "ok"


# ── Per-model drift checks ────────────────────────────────────────────────────


def check_intent_classifier_drift(
    baseline_proba: np.ndarray,
    current_proba: np.ndarray,
    baseline_label_counts: dict[str, int] | None = None,
    current_label_counts: dict[str, int] | None = None,
) -> list[DriftResult]:
    """
    PSI across each intent class confidence column (8 classes).
    Optional chi-square on observed label distributions.

    baseline_proba / current_proba: (N, 8) arrays of predict_proba() output.
    """
    results: list[DriftResult] = []
    thresholds = _load_thresholds().get("models", {}).get("intent_classifier", {})

    if baseline_proba.size > 0 and current_proba.size > 0:
        n_classes = baseline_proba.shape[1]
        for col in range(n_classes):
            psi = compute_psi(baseline_proba[:, col], current_proba[:, col])
            results.append(DriftResult(
                model_name="intent_classifier",
                metric_type="psi",
                metric_value=round(psi, 4),
                status=_psi_status(psi, thresholds),
                details=f"class_{col}_confidence_psi={psi:.4f}",
            ))

    if baseline_label_counts and current_label_counts:
        stat, pval = compute_chi_square(baseline_label_counts, current_label_counts)
        status = "severe" if pval < 0.01 else ("warning" if pval < 0.05 else "ok")
        results.append(DriftResult(
            model_name="intent_classifier",
            metric_type="chi_square",
            metric_value=round(stat, 4),
            status=status,
            details=f"label_distribution chi2={stat:.4f} p={pval:.4f}",
        ))

    return results


def check_tone_classifier_drift(
    baseline_proba: np.ndarray,
    current_proba: np.ndarray,
) -> list[DriftResult]:
    """
    PSI across each tone class confidence column (3 classes: gentle/neutral/firm).

    baseline_proba / current_proba: (N, 3) arrays of predict_proba() output.
    """
    results: list[DriftResult] = []
    thresholds = _load_thresholds().get("models", {}).get("tone_classifier", {})

    if baseline_proba.size > 0 and current_proba.size > 0:
        n_classes = baseline_proba.shape[1]
        for col in range(n_classes):
            psi = compute_psi(baseline_proba[:, col], current_proba[:, col])
            results.append(DriftResult(
                model_name="tone_classifier",
                metric_type="psi",
                metric_value=round(psi, 4),
                status=_psi_status(psi, thresholds),
                details=f"class_{col}_confidence_psi={psi:.4f}",
            ))

    return results


def check_embedding_drift(
    baseline_centroid: np.ndarray,
    current_centroid: np.ndarray,
    model_name: str = "product_embeddings",
) -> DriftResult:
    """
    Cosine distance between product embedding centroids.
    Used to detect shifts in the embedding space (e.g. after re-embedding with a new model).
    """
    drift = compute_cosine_drift(baseline_centroid, current_centroid)
    status = "severe" if drift >= 0.20 else ("warning" if drift >= 0.10 else "ok")
    return DriftResult(
        model_name=model_name,
        metric_type="cosine",
        metric_value=round(drift, 4),
        status=status,
        details=f"cosine_distance={drift:.4f}",
    )


# ── Aggregator ────────────────────────────────────────────────────────────────


def run_drift_report(results: list[DriftResult]) -> DriftReport:
    """
    Aggregate a list of DriftResults into a single DriftReport.
    overall_status is the worst individual status found.
    """
    if not results:
        return DriftReport(results=[], overall_status="ok", checked_models=[])

    statuses = [r.status for r in results]
    if "severe" in statuses:
        overall = "severe"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    checked = sorted({r.model_name for r in results})
    return DriftReport(results=results, overall_status=overall, checked_models=checked)
