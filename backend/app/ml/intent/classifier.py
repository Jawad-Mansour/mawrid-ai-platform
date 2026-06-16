"""
Feature:  AI Chatbot — 3-Tier Intent Classifier
Layer:    ML / Intent
Module:   app.ml.intent.classifier
Purpose:  3-tier cascade pipeline:
          Tier 1: TF-IDF + LR (< 5ms, 8 classes, confidence threshold 0.70)
          Tier 2: DistilBERT ONNX (< 100ms, only if Tier 1 < 0.70; skipped if
                  ml_models/intent_tier2/ does not exist)
          Tier 3: GPT-4o zero-shot (only if Tier 1+2 confidence both < threshold)
          Result includes which tier resolved the classification.
          Guardrails: out_of_scope → reject before LLM call.
Depends:  app.ml.intent.tier1, app.ml.intent.tier2, app.infra.llm.openai
HITL:     None — classification is internal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.ml.intent import tier1, tier2

logger = logging.getLogger(__name__)

INTENT_CLASSES = [
    "product_search",
    "order_status",
    "stock_check",
    "shipment_status",
    "invoice_query",
    "dunning_action",
    "complex_task",
    "out_of_scope",
]

# Intent classes that map to direct DB query (no RAG/Supervisor needed)
DIRECT_QUERY_INTENTS = {
    "order_status",
    "stock_check",
    "shipment_status",
    "invoice_query",
    "dunning_action",
}

# Intent classes that use the RAG pipeline
RAG_INTENTS = {"product_search"}

# Intent classes that route to LangGraph Supervisor
AGENT_INTENTS = {"complex_task"}


@dataclass
class ClassificationResult:
    intent: str
    confidence: float
    tier_used: int  # 1, 2, or 3
    latency_ms: float
    route: str  # "rag" | "direct_query" | "agent" | "rejected"
    tier1_latency_ms: float = 0.0
    tier2_latency_ms: float = 0.0
    tier3_latency_ms: float = 0.0
    raw_scores: dict[str, float] = field(default_factory=dict)


async def classify(text: str) -> ClassificationResult:
    """
    Run the 3-tier cascade. Returns the first tier that exceeds its threshold.
    Always returns a result — Tier 3 (GPT-4o) is the guaranteed fallback.
    """
    total_t1_ms = 0.0
    total_t2_ms = 0.0
    total_t3_ms = 0.0

    # Tier 1
    t1_result = tier1.predict(text)
    total_t1_ms = t1_result.latency_ms

    # Safety net against false rejections: a confident-but-wrong Tier 1 must never
    # reject a real business question on its own. We never trust an out_of_scope
    # verdict from the cheap tiers — always escalate it to GPT-4o (the scope authority).
    t1_trustworthy = not t1_result.escalate and t1_result.intent != "out_of_scope"

    if t1_trustworthy:
        return ClassificationResult(
            intent=t1_result.intent,
            confidence=t1_result.confidence,
            tier_used=1,
            latency_ms=total_t1_ms,
            tier1_latency_ms=total_t1_ms,
            route=_route_for_intent(t1_result.intent),
        )

    # Tier 2 (only if ONNX model is available)
    t2_result = tier2.predict(text)
    if t2_result is not None:
        total_t2_ms = t2_result.latency_ms
        t2_trustworthy = not t2_result.escalate and t2_result.intent != "out_of_scope"
        if t2_trustworthy:
            return ClassificationResult(
                intent=t2_result.intent,
                confidence=t2_result.confidence,
                tier_used=2,
                latency_ms=total_t1_ms + total_t2_ms,
                tier1_latency_ms=total_t1_ms,
                tier2_latency_ms=total_t2_ms,
                route=_route_for_intent(t2_result.intent),
            )

    # Tier 3: GPT-4o zero-shot
    t3_intent, t3_confidence, t3_ms = await _tier3_classify(text)
    total_t3_ms = t3_ms

    return ClassificationResult(
        intent=t3_intent,
        confidence=t3_confidence,
        tier_used=3,
        latency_ms=total_t1_ms + total_t2_ms + total_t3_ms,
        tier1_latency_ms=total_t1_ms,
        tier2_latency_ms=total_t2_ms,
        tier3_latency_ms=total_t3_ms,
        route=_route_for_intent(t3_intent),
    )


def classify_sync(text: str) -> ClassificationResult:
    """
    Synchronous Tier 1 only — for use in non-async contexts.
    Returns escalate=False Tier 1 result; caller must await classify() for full cascade.
    """
    t1 = tier1.predict(text)
    return ClassificationResult(
        intent=t1.intent,
        confidence=t1.confidence,
        tier_used=1,
        latency_ms=t1.latency_ms,
        tier1_latency_ms=t1.latency_ms,
        route=_route_for_intent(t1.intent),
    )


def _route_for_intent(intent: str) -> str:
    if intent == "out_of_scope":
        return "rejected"
    if intent in RAG_INTENTS:
        return "rag"
    if intent in DIRECT_QUERY_INTENTS:
        return "direct_query"
    if intent in AGENT_INTENTS:
        return "agent"
    return "rag"  # default for unrecognised labels


async def _tier3_classify(text: str) -> tuple[str, float, float]:
    """
    GPT-4o zero-shot fallback. Returns (intent, confidence, latency_ms).
    Falls back to the Tier 1 best guess on any error.
    """
    import time  # noqa: PLC0415

    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    system_prompt = (
        "You are an intent classifier for an importer/distributor operations platform.\n"
        "Classify the user message into exactly ONE of these classes:\n"
        "- product_search: find products, product details, specs, recommendations\n"
        "- stock_check: inventory and quantities — 'how many products/items', stock levels, what's in the catalog\n"
        "- order_status: status of a purchase order to a supplier\n"
        "- shipment_status: tracking shipments, deliveries, ETAs\n"
        "- invoice_query: invoices, payments, amounts owed, overdue, receivables/payables\n"
        "- dunning_action: payment reminders, collections, chasing late payers\n"
        "- complex_task: multi-step requests (draft a PO, contact a supplier, run enrichment)\n"
        "- out_of_scope: greetings, small talk, or anything unrelated to the business\n"
        "If the message relates to the business's products, inventory, orders, suppliers, "
        "invoices or shipments, prefer the closest in-scope class over out_of_scope.\n"
        "Reply with ONLY the class name and nothing else."
    )

    t0 = time.perf_counter()
    try:
        response = await chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            model="gpt-4o-mini",  # cheapest tier for classification
            max_tokens=20,
            temperature=0.0,
        )
        raw = response.strip().lower().replace("-", "_")
        intent = raw if raw in INTENT_CLASSES else "out_of_scope"
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return intent, 0.95, latency_ms  # GPT-4o result treated as high-confidence
    except Exception as exc:
        logger.warning("intent_tier3_failed", extra={"error": str(exc)})
        latency_ms = (time.perf_counter() - t0) * 1000.0
        # Fall back to Tier 1's best guess
        t1 = tier1.predict(text)
        return t1.intent, t1.confidence, latency_ms
