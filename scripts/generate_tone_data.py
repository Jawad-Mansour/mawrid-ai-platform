"""
Feature:  Dunning Engine — Tone Classifier Training Data
Layer:    Scripts / Data Generation
Module:   scripts.generate_tone_data
Purpose:  Generates 240 labeled tone training examples (80 per class:
          gentle / neutral / firm). Uses deterministic priority-ordered rules
          based on: days_overdue, customer_segment (VIP/Regular/At-Risk/Dormant),
          overdue_amount, payment_history_score, previous_dunning_count.
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
    """Priority-ordered rules — first match wins."""
    # P1: barely overdue → always gentle regardless of segment
    if days_overdue <= 7:
        return "gentle"
    # P2: VIP → always gentle (relationship preservation)
    if customer_segment == "VIP":
        return "gentle"
    # P3: At-Risk/Dormant, long overdue, already dunned → firm
    if customer_segment in ("At-Risk", "Dormant") and days_overdue >= 14 and previous_dunning_count >= 2:
        return "firm"
    # P4: historically reliable payer → gentle
    if payment_history_score >= 0.8:
        return "gentle"
    # Default
    return "neutral"


def generate_examples(target_per_class: int = 80, seed: int = 42) -> list[dict]:
    random.seed(seed)
    examples: list[dict] = []

    # Parameter ranges that reliably produce each label under the priority rules
    class_params = {
        "gentle": [
            # P1 triggers: days_overdue ≤ 7, any segment
            {"days_range": (0, 7), "segment": "Regular", "score_range": (0.0, 1.0), "dunning_range": (0, 5)},
            # P2 triggers: VIP, any overdue, any history
            {"days_range": (8, 60), "segment": "VIP", "score_range": (0.0, 0.79), "dunning_range": (0, 1)},
            # P4 triggers: good payer, not At-Risk/Dormant, days > 7
            {"days_range": (8, 13), "segment": "Regular", "score_range": (0.8, 1.0), "dunning_range": (0, 1)},
        ],
        "firm": [
            # P3 triggers: At-Risk/Dormant, ≥14 days, ≥2 dunning attempts
            {"days_range": (14, 90), "segment": "At-Risk", "score_range": (0.0, 0.79), "dunning_range": (2, 5)},
            {"days_range": (14, 90), "segment": "Dormant", "score_range": (0.0, 0.79), "dunning_range": (2, 5)},
        ],
        "neutral": [
            # Default: days > 7, not VIP, not P3, score < 0.8
            {"days_range": (8, 60), "segment": "Regular", "score_range": (0.0, 0.79), "dunning_range": (0, 1)},
            {"days_range": (8, 13), "segment": "At-Risk", "score_range": (0.0, 0.79), "dunning_range": (0, 1)},
            {"days_range": (8, 13), "segment": "Dormant", "score_range": (0.0, 0.79), "dunning_range": (0, 1)},
        ],
    }

    for tone, param_list in class_params.items():
        count = 0
        attempts = 0
        while count < target_per_class and attempts < target_per_class * 20:
            attempts += 1
            params = random.choice(param_list)
            days = random.randint(*params["days_range"])
            segment = params["segment"]
            score = round(random.uniform(*params["score_range"]), 2)
            dunning_count = random.randint(*params["dunning_range"])
            overdue_amount = round(random.uniform(50, 20000), 2)

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

    return examples


if __name__ == "__main__":
    examples = generate_examples()

    counts: dict[str, int] = {"gentle": 0, "neutral": 0, "firm": 0}
    for e in examples:
        counts[e["tone"]] += 1
    print(f"Generated: {counts}")
    assert all(v == 80 for v in counts.values()), f"Class imbalance: {counts}"

    out_path = (
        Path(__file__).parent.parent
        / "backend" / "tests" / "evals" / "eval_dataset" / "tone_training_data.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(examples, indent=2))
    print(f"Saved {len(examples)} examples to {out_path}")
