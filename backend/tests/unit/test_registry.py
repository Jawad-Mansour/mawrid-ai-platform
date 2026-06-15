"""
Feature:  MLOps Governance
Layer:    Tests / Unit
Module:   tests.unit.test_registry
Purpose:  Unit tests for SHA-256 artifact verification and champion/challenger
          gating.  MLflow calls are mocked — no server required.
Depends:  app.ml.registry
HITL:     None.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.ml.registry import (
    ModelRecord,
    champion_challenger_gate,
    compute_sha256,
    verify_sha256,
)

# ── compute_sha256 ────────────────────────────────────────────────────────────


class TestComputeSha256:
    def test_known_hash(self, tmp_path: Path) -> None:
        content = b"hello mawrid"
        expected = hashlib.sha256(content).hexdigest()
        f = tmp_path / "artifact.pkl"
        f.write_bytes(content)
        assert compute_sha256(f) == expected

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.pkl"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(f) == expected

    def test_large_file_chunked(self, tmp_path: Path) -> None:
        content = b"x" * 200_000  # larger than 64 KiB chunk size
        expected = hashlib.sha256(content).hexdigest()
        f = tmp_path / "large.pkl"
        f.write_bytes(content)
        assert compute_sha256(f) == expected


# ── verify_sha256 ─────────────────────────────────────────────────────────────


class TestVerifySha256:
    def test_matching_hash_returns_true(self, tmp_path: Path) -> None:
        content = b"model weights"
        f = tmp_path / "model.pkl"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert verify_sha256(f, expected) is True

    def test_mismatched_hash_returns_false(self, tmp_path: Path) -> None:
        f = tmp_path / "model.pkl"
        f.write_bytes(b"real weights")
        wrong_hash = hashlib.sha256(b"different data").hexdigest()
        assert verify_sha256(f, wrong_hash) is False

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.pkl"
        assert verify_sha256(missing, "abcdef1234") is False


# ── champion_challenger_gate ──────────────────────────────────────────────────


class TestChampionChallengerGate:
    def test_better_challenger_passes(self) -> None:
        new = {"weighted_f1": 0.92}
        champion = {"weighted_f1": 0.88}
        assert champion_challenger_gate(new, champion, "weighted_f1") is True

    def test_equal_challenger_passes_within_tolerance(self) -> None:
        metrics = {"weighted_f1": 0.88}
        assert champion_challenger_gate(metrics, metrics, "weighted_f1") is True

    def test_worse_challenger_rejected(self) -> None:
        new = {"weighted_f1": 0.80}
        champion = {"weighted_f1": 0.88}
        assert champion_challenger_gate(new, champion, "weighted_f1") is False

    def test_tolerance_boundary(self) -> None:
        # new is within 0.001 of champion → should pass
        new = {"weighted_f1": 0.8790}
        champion = {"weighted_f1": 0.8800}
        # 0.8800 - 0.001 = 0.8790 → passes
        assert champion_challenger_gate(new, champion, "weighted_f1") is True

    def test_lower_is_better_better_mae_passes(self) -> None:
        new = {"test_mae": 3.5}
        champion = {"test_mae": 4.0}
        assert champion_challenger_gate(new, champion, "test_mae", higher_is_better=False) is True

    def test_lower_is_better_worse_mae_rejected(self) -> None:
        new = {"test_mae": 5.0}
        champion = {"test_mae": 4.0}
        assert champion_challenger_gate(new, champion, "test_mae", higher_is_better=False) is False

    def test_missing_new_metric_rejected(self) -> None:
        assert champion_challenger_gate({}, {"weighted_f1": 0.88}, "weighted_f1") is False

    def test_missing_champion_metric_rejected(self) -> None:
        assert champion_challenger_gate({"weighted_f1": 0.90}, {}, "weighted_f1") is False


# ── ModelRecord ───────────────────────────────────────────────────────────────


class TestModelRecord:
    def test_instantiation(self) -> None:
        rec = ModelRecord(
            name="tone_classifier",
            version="3",
            stage="production",
            sha256_hash="abc123",
            metrics={"weighted_f1": 0.87},
        )
        assert rec.name == "tone_classifier"
        assert rec.stage == "production"
        assert rec.metrics["weighted_f1"] == 0.87
