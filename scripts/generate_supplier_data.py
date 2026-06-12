"""
Feature:  Supplier Intelligence
Layer:    ML / Data Generation
Module:   scripts.generate_supplier_data
Purpose:  Generates 2000 synthetic supplier training examples for Ridge regression
          scorer. Uses the deterministic 6-feature formula as ground-truth labels
          with small Gaussian noise to simulate real measurement variation.
          Covers boundary conditions (perfect, terrible, and mixed suppliers).
          Output: backend/tests/evals/eval_dataset/supplier_training_data.json
Run with: uv run python scripts/generate_supplier_data.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

OUTPUT_PATH = (
    Path(__file__).parent.parent
    / "backend" / "tests" / "evals" / "eval_dataset" / "supplier_training_data.json"
)

random.seed(42)

_BUCKETS = [
    # (weight, on_time_range, damage_range, price_range, response_range, disc_range, completeness_range)
    # Excellent suppliers
    (200, (0.90, 1.00), (0.00, 0.02), (0.90, 1.05), (0.0, 12.0), (0.00, 0.02), (0.80, 1.00)),
    # Good suppliers
    (400, (0.75, 0.95), (0.00, 0.05), (0.95, 1.10), (8.0, 36.0), (0.00, 0.05), (0.50, 1.00)),
    # Average suppliers
    (600, (0.55, 0.80), (0.02, 0.10), (0.98, 1.20), (24.0, 72.0), (0.03, 0.10), (0.33, 0.75)),
    # Below-average suppliers
    (400, (0.35, 0.65), (0.05, 0.20), (1.00, 1.40), (48.0, 120.0), (0.05, 0.20), (0.33, 0.67)),
    # Poor suppliers
    (200, (0.00, 0.45), (0.10, 0.50), (1.10, 2.00), (72.0, 168.0), (0.10, 0.40), (0.33, 0.50)),
    # Boundary cases near thresholds
    (200, (0.88, 0.92), (0.04, 0.06), (0.99, 1.01), (23.0, 25.0), (0.04, 0.06), (0.65, 0.70)),
]


def _formula(
    on_time: float,
    damage: float,
    price: float,
    response: float,
    discrepancy: float,
    completeness: float,
) -> float:
    score = 100.0
    score -= (1.0 - on_time) * 40.0
    score -= damage * 30.0
    score -= max(0.0, price - 1.0) * 15.0
    score -= min(response / 168.0, 1.0) * 10.0
    score -= discrepancy * 5.0
    score -= (1.0 - completeness) * 5.0
    return max(0.0, min(100.0, score))


def _sample(lo: float, hi: float) -> float:
    return lo + random.random() * (hi - lo)


def generate(n: int = 2000) -> list[dict[str, float]]:
    examples: list[dict[str, float]] = []

    # Boundary anchors (deterministic, no noise)
    anchors = [
        (1.0, 0.0, 1.0, 0.0, 0.0, 1.0),   # perfect → 100
        (0.0, 1.0, 2.0, 168.0, 1.0, 0.33), # terrible → ~0
        (0.8, 0.02, 1.0, 24.0, 0.0, 0.67), # default-ish → ~80
    ]
    for a in anchors:
        score = _formula(*a)
        examples.append({
            "on_time_delivery_rate": a[0], "damage_rate": a[1],
            "avg_price_vs_market": a[2], "response_time_hours": a[3],
            "discrepancy_rate": a[4], "catalog_completeness": a[5],
            "score": round(score, 4),
        })

    # Weighted bucket sampling
    total_weight = sum(b[0] for b in _BUCKETS)
    for _ in range(n - len(anchors)):
        r = random.random() * total_weight
        cumulative = 0.0
        bucket = _BUCKETS[-1]
        for b in _BUCKETS:
            cumulative += b[0]
            if r <= cumulative:
                bucket = b
                break

        _, otr, dr, pr, rr, discr, cr = bucket
        on_time = max(0.0, min(1.0, _sample(*otr)))
        damage = max(0.0, min(1.0, _sample(*dr)))
        price = max(0.5, _sample(*pr))
        response = max(0.0, min(168.0, _sample(*rr)))
        discrepancy = max(0.0, min(1.0, _sample(*discr)))
        completeness = max(0.0, min(1.0, _sample(*cr)))

        base_score = _formula(on_time, damage, price, response, discrepancy, completeness)
        # Small Gaussian noise to simulate real measurement variation
        noise = random.gauss(0.0, 1.5)
        score = max(0.0, min(100.0, base_score + noise))

        examples.append({
            "on_time_delivery_rate": round(on_time, 4),
            "damage_rate": round(damage, 4),
            "avg_price_vs_market": round(price, 4),
            "response_time_hours": round(response, 2),
            "discrepancy_rate": round(discrepancy, 4),
            "catalog_completeness": round(completeness, 4),
            "score": round(score, 4),
        })

    random.shuffle(examples)
    return examples


if __name__ == "__main__":
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = generate(2000)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data)} examples to {OUTPUT_PATH}")
