"""
Feature:  Supplier Intelligence
Layer:    ML / Supplier Scorer
Module:   app.ml.supplier_scorer.scorer
Purpose:  Supplier scoring: deterministic formula (primary) + Ridge regression
          (ML model loaded from pickle if available). Formula acts as both the
          ground-truth label generator for training and the production fallback.
          Score range: 0–100 (100 = perfect supplier).
          6 features: on_time_delivery_rate, damage_rate, avg_price_vs_market,
          response_time_hours, discrepancy_rate, catalog_completeness.
Depends:  app.infra.db.models.delivery_event, joblib, numpy
HITL:     None — ML inference only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:
    from app.infra.db.models.delivery_event import SupplierDeliveryEvent

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "ml_models" / "supplier_scorer.pkl"

# Loaded at first call, None if pkl not present
_bundle: dict[str, Any] | None = None


@dataclass(frozen=True)
class SupplierFeatures:
    on_time_delivery_rate: float  # 0.0–1.0; fraction of on-time deliveries
    damage_rate: float  # 0.0–1.0; items_damaged / items_received
    avg_price_vs_market: float  # ratio; 1.0 = at market, >1.0 = over-priced
    response_time_hours: float  # avg hours supplier takes to confirm PO
    discrepancy_rate: float  # fraction of deliveries short by > 5%
    catalog_completeness: float  # 0.0–1.0; fraction of profile fields filled


@dataclass
class ScorerResult:
    score: float  # 0–100
    features: SupplierFeatures
    method: str  # "formula" | "ridge"
    sample_count: int  # number of delivery events used


def compute_score_formula(features: SupplierFeatures) -> float:
    """Deterministic 6-feature formula. Used as training labels and fallback."""
    score = 100.0
    score -= (1.0 - features.on_time_delivery_rate) * 40.0
    score -= features.damage_rate * 30.0
    score -= max(0.0, features.avg_price_vs_market - 1.0) * 15.0
    score -= min(features.response_time_hours / 168.0, 1.0) * 10.0
    score -= features.discrepancy_rate * 5.0
    score -= (1.0 - features.catalog_completeness) * 5.0
    return float(max(0.0, min(100.0, score)))


def _load_bundle() -> dict[str, Any] | None:
    global _bundle
    if _bundle is not None:
        return _bundle
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib  # noqa: PLC0415

        _bundle = joblib.load(MODEL_PATH)
        logger.info("supplier_scorer_model_loaded", extra={"path": str(MODEL_PATH)})
    except Exception as exc:
        logger.warning("supplier_scorer_load_failed", extra={"error": str(exc)})
        _bundle = None
    return _bundle


def score_supplier(features: SupplierFeatures, sample_count: int = 0) -> ScorerResult:
    """Compute supplier score. Uses Ridge model if available, formula fallback otherwise."""
    bundle = _load_bundle()
    if bundle is not None:
        try:
            scaler = bundle["scaler"]
            ridge = bundle["ridge"]
            feat_arr = np.array(
                [
                    [
                        features.on_time_delivery_rate,
                        features.damage_rate,
                        features.avg_price_vs_market,
                        features.response_time_hours,
                        features.discrepancy_rate,
                        features.catalog_completeness,
                    ]
                ]
            )
            scaled = scaler.transform(feat_arr)
            raw = float(ridge.predict(scaled)[0])
            score = max(0.0, min(100.0, raw))
            return ScorerResult(
                score=score, features=features, method="ridge", sample_count=sample_count
            )
        except Exception as exc:
            logger.warning("supplier_scorer_ridge_failed", extra={"error": str(exc)})

    score = compute_score_formula(features)
    return ScorerResult(score=score, features=features, method="formula", sample_count=sample_count)


def extract_features(
    events: list[SupplierDeliveryEvent],
    supplier_email: str | None,
    supplier_phone: str | None,
) -> SupplierFeatures:
    """
    Derive the 6 scorer features from delivery event history.
    Called after every goods-receiving event to keep the score current.
    """
    if not events:
        completeness = _catalog_completeness(supplier_email, supplier_phone)
        return SupplierFeatures(
            on_time_delivery_rate=0.8,
            damage_rate=0.0,
            avg_price_vs_market=1.0,
            response_time_hours=24.0,
            discrepancy_rate=0.0,
            catalog_completeness=completeness,
        )

    total = len(events)
    on_time = sum(
        1 for e in events if e.delivered_date is not None and e.delivered_date <= e.promised_date
    )
    on_time_rate = on_time / total

    total_received = sum(e.items_received or 0 for e in events) or 1
    total_damaged = sum(e.items_damaged or 0 for e in events)
    damage_rate = total_damaged / total_received

    priced = [e for e in events if e.price_billed is not None and e.price_agreed > 0]
    avg_price = (
        sum(cast(float, e.price_billed) / e.price_agreed for e in priced) / len(priced)
        if priced
        else 1.0
    )

    timed = [e for e in events if e.response_time_hours is not None]
    response_hours = (
        sum(cast(float, e.response_time_hours) for e in timed) / len(timed) if timed else 24.0
    )

    discrepant = sum(
        1 for e in events if e.items_ordered > 0 and e.items_received < e.items_ordered * 0.95
    )
    discrepancy_rate = discrepant / total

    completeness = _catalog_completeness(supplier_email, supplier_phone)

    return SupplierFeatures(
        on_time_delivery_rate=on_time_rate,
        damage_rate=damage_rate,
        avg_price_vs_market=avg_price,
        response_time_hours=response_hours,
        discrepancy_rate=discrepancy_rate,
        catalog_completeness=completeness,
    )


def _catalog_completeness(email: str | None, phone: str | None) -> float:
    """Fraction of supplier contact fields filled: name (always) + email + phone."""
    filled = 1  # name is always present
    if email:
        filled += 1
    if phone:
        filled += 1
    return filled / 3.0
