"""
Feature:  Dunning Engine — Tone Classifier Training Data
Layer:    Scripts / Data Generation
Module:   scripts.generate_tone_data
Purpose:  Generates 3000 labeled tone training examples (1000 per class:
          gentle / neutral / firm). Uses deterministic priority-ordered rules
          based on: days_overdue, customer_segment (VIP/Regular/At-Risk/Dormant),
          overdue_amount, payment_history_score, previous_dunning_count.
          Large dataset (1000/class) provides robust feature-space coverage,
          especially for boundary conditions between classes.
          Output: backend/tests/evals/eval_dataset/tone_training_data.json.
          Run with: uv run python scripts/generate_tone_data.py
Depends:  None (stdlib only)
HITL:     None.
"""
import json
import random
from pathlib import Path


def determine_tone(
    days_overdue: int,
    customer_segment: str,
    payment_history_score: float,
    previous_dunning_count: int,
) -> str:
    """Priority-ordered rules — first match wins. Ground truth for training labels."""
    # P1: barely overdue → always gentle regardless of segment or history
    if days_overdue <= 7:
        return "gentle"
    # P2: VIP → always gentle (relationship preservation, even if very overdue)
    if customer_segment == "VIP":
        return "gentle"
    # P3: At-Risk/Dormant, seriously overdue, repeatedly dunned → firm
    if (
        customer_segment in ("At-Risk", "Dormant")
        and days_overdue >= 14
        and previous_dunning_count >= 2
    ):
        return "firm"
    # P4: historically reliable payer → gentle (trust their track record)
    if payment_history_score >= 0.8:
        return "gentle"
    # Default: not gentle, not firm → neutral
    return "neutral"


# Parameter configuration for generating each class with good feature-space coverage.
# Each bucket is a parameter space that reliably produces the target label.
# Multiple buckets per class ensure variation across the feature space.
_CLASS_PARAMS: dict[str, list[dict]] = {
    "gentle": [
        # P1 — barely overdue (0-7 days), any segment, any history
        {"days_range": (0, 7), "segments": ["Regular", "At-Risk", "Dormant", "VIP"],
         "score_range": (0.0, 1.0), "dunning_range": (0, 5), "weight": 4},
        # P2 — VIP, any overdue, score below P4 threshold (to test P2 beats P4)
        {"days_range": (8, 90), "segments": ["VIP"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 5), "weight": 3},
        # P2+P4 — VIP with good history (both rules fire; P2 wins but label is same)
        {"days_range": (8, 90), "segments": ["VIP"],
         "score_range": (0.8, 1.0), "dunning_range": (0, 5), "weight": 2},
        # P4 — good payer, not VIP, days 8-13 (can't trigger P3 at 8-13 even if At-Risk)
        {"days_range": (8, 13), "segments": ["Regular", "At-Risk", "Dormant"],
         "score_range": (0.8, 1.0), "dunning_range": (0, 1), "weight": 3},
        # P4 — good payer, Regular, any overdue (never triggers P3 since Regular is not At-Risk)
        {"days_range": (8, 90), "segments": ["Regular"],
         "score_range": (0.8, 1.0), "dunning_range": (0, 5), "weight": 4},
        # P4 — good payer, At-Risk/Dormant, days 14+, dunning < 2 (P3 doesn't fire → P4 applies)
        {"days_range": (14, 90), "segments": ["At-Risk", "Dormant"],
         "score_range": (0.8, 1.0), "dunning_range": (0, 1), "weight": 2},
    ],
    "firm": [
        # P3 triggers — At-Risk, ≥14 days, ≥2 dunning attempts
        {"days_range": (14, 30), "segments": ["At-Risk"],
         "score_range": (0.0, 0.79), "dunning_range": (2, 3), "weight": 3},
        {"days_range": (31, 60), "segments": ["At-Risk"],
         "score_range": (0.0, 0.79), "dunning_range": (2, 4), "weight": 3},
        {"days_range": (61, 90), "segments": ["At-Risk"],
         "score_range": (0.0, 0.79), "dunning_range": (3, 5), "weight": 2},
        # P3 triggers — Dormant, ≥14 days, ≥2 dunning attempts
        {"days_range": (14, 30), "segments": ["Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (2, 3), "weight": 3},
        {"days_range": (31, 60), "segments": ["Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (2, 4), "weight": 3},
        {"days_range": (61, 90), "segments": ["Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (3, 5), "weight": 2},
        # Boundary: exactly day 14, dunning_count=2 (minimum P3 threshold)
        {"days_range": (14, 14), "segments": ["At-Risk", "Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (2, 2), "weight": 2},
    ],
    "neutral": [
        # Default: days > 7, not VIP, not P3, score < 0.8
        # Regular segment — can never trigger P3
        {"days_range": (8, 20), "segments": ["Regular"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 1), "weight": 4},
        {"days_range": (21, 60), "segments": ["Regular"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 3), "weight": 3},
        {"days_range": (61, 90), "segments": ["Regular"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 5), "weight": 2},
        # At-Risk/Dormant but dunning_count < 2 (P3 not triggered) and score < 0.8 (P4 not triggered)
        {"days_range": (8, 13), "segments": ["At-Risk", "Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 1), "weight": 3},
        {"days_range": (14, 60), "segments": ["At-Risk", "Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (0, 1), "weight": 3},
        # Boundary: At-Risk, day 14, dunning_count=1 (just below P3 threshold)
        {"days_range": (14, 20), "segments": ["At-Risk", "Dormant"],
         "score_range": (0.0, 0.79), "dunning_range": (1, 1), "weight": 3},
    ],
}


def _weighted_choice(params_with_weight: list[dict], rng: random.Random) -> dict:
    """Pick a parameter bucket proportional to its weight."""
    weights = [p["weight"] for p in params_with_weight]
    return rng.choices(params_with_weight, weights=weights, k=1)[0]


def generate_examples(target_per_class: int = 1000, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    examples: list[dict] = []

    for tone, param_list in _CLASS_PARAMS.items():
        count = 0
        max_attempts = target_per_class * 50  # generous retry budget
        attempts = 0

        while count < target_per_class and attempts < max_attempts:
            attempts += 1
            params = _weighted_choice(param_list, rng)
            days = rng.randint(*params["days_range"])
            segment = rng.choice(params["segments"])
            score = round(rng.uniform(*params["score_range"]), 2)
            dunning_count = rng.randint(*params["dunning_range"])
            overdue_amount = round(rng.uniform(50.0, 25000.0), 2)

            predicted = determine_tone(days, segment, score, dunning_count)
            if predicted == tone:
                examples.append({
                    "days_overdue": days,
                    "customer_segment": segment,
                    "overdue_amount": overdue_amount,
                    "payment_history_score": score,
                    "previous_dunning_count": dunning_count,
                    "tone": tone,
                })
                count += 1

        if count < target_per_class:
            raise RuntimeError(
                f"Could only generate {count}/{target_per_class} '{tone}' examples "
                f"after {attempts} attempts. Check parameter buckets."
            )

    # Shuffle so classes aren't in blocks (important for cross-validation)
    rng.shuffle(examples)
    return examples


if __name__ == "__main__":
    target = 1000
    examples = generate_examples(target_per_class=target)

    counts: dict[str, int] = {"gentle": 0, "neutral": 0, "firm": 0}
    for e in examples:
        counts[e["tone"]] += 1

    print(f"Generated {len(examples)} total examples:")
    for cls, n in counts.items():
        print(f"  {cls}: {n}")

    assert all(v == target for v in counts.values()), f"Class imbalance: {counts}"

    out_path = (
        Path(__file__).parent.parent
        / "backend" / "tests" / "evals" / "eval_dataset" / "tone_training_data.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(examples, indent=2))
    print(f"\nSaved {len(examples)} examples to {out_path}")
