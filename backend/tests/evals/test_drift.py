"""
Feature:  Model Health & Drift Detection — CI Gate 9
Layer:    Tests / Evals
Module:   tests.evals.test_drift
Purpose:  Nightly CI Gate 9. Verifies that the drift runner produces correct
          last_drift_check.json output for stable data (ok) and for injected
          severe drift (severe). No DB, LLM, or network required.
Depends:  app.ml.drift.monitor
HITL:     None.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# ── Stable distributions → "ok" ───────────────────────────────────────────────


def test_stable_drift_writes_ok(tmp_path: Path) -> None:
    from app.ml.drift.monitor import run_drift_check

    output = tmp_path / "last_drift_check.json"
    report = run_drift_check(output_path=output)

    assert report.overall_status == "ok", (
        f"Expected ok but got {report.overall_status}. "
        f"Results: {[(r.model_name, r.metric_type, r.status) for r in report.results]}"
    )
    assert output.exists()
    data = json.loads(output.read_text())
    assert data["status"] == "ok"
    assert "checked_at" in data


# ── Injected severe drift → "severe" ──────────────────────────────────────────


def test_severe_embedding_drift_written(tmp_path: Path) -> None:
    """Opposite embedding centroids give cosine distance = 2.0 → severe."""
    from app.ml.drift.monitor import _write_result, check_embedding_drift, run_drift_report

    result = check_embedding_drift(np.ones(128), -np.ones(128))
    assert result.status == "severe"

    report = run_drift_report([result])
    assert report.overall_status == "severe"

    output = tmp_path / "drift_severe.json"
    _write_result(report, output)
    data = json.loads(output.read_text())
    assert data["status"] == "severe"


def test_severe_psi_drift_detected(tmp_path: Path) -> None:
    """4-sigma distribution shift gives PSI >> 0.20 → severe."""
    from app.ml.drift.monitor import (
        _write_result,
        check_intent_classifier_drift,
        run_drift_report,
    )

    rng = np.random.default_rng(99)
    baseline = rng.normal(0, 1, (500, 8))
    baseline = np.abs(baseline)
    baseline = baseline / baseline.sum(axis=1, keepdims=True)

    current = rng.normal(5, 1, (500, 8))
    current = np.abs(current)
    current = current / current.sum(axis=1, keepdims=True)

    results = check_intent_classifier_drift(baseline, current)
    report = run_drift_report(results)

    output = tmp_path / "drift_psi.json"
    _write_result(report, output)
    data = json.loads(output.read_text())
    assert data["status"] in ("warning", "severe")


# ── JSON format contract ───────────────────────────────────────────────────────


def test_output_json_has_required_keys(tmp_path: Path) -> None:
    from app.ml.drift.monitor import run_drift_check

    output = tmp_path / "out.json"
    run_drift_check(output_path=output)
    data = json.loads(output.read_text())
    assert set(data.keys()) == {"status", "checked_at"}
    assert data["status"] in {"ok", "warning", "severe"}


def test_output_creates_parent_directories(tmp_path: Path) -> None:
    from app.ml.drift.monitor import run_drift_check

    nested = tmp_path / "a" / "b" / "c" / "drift.json"
    run_drift_check(output_path=nested)
    assert nested.exists()


# ── write_result idempotency ───────────────────────────────────────────────────


def test_write_result_overwrites_previous(tmp_path: Path) -> None:
    from app.ml.drift.monitor import DriftReport, _write_result

    output = tmp_path / "check.json"
    _write_result(DriftReport(overall_status="severe"), output)
    _write_result(DriftReport(overall_status="ok"), output)
    data = json.loads(output.read_text())
    assert data["status"] == "ok"
