"""
Feature:  Supplier Intelligence
Layer:    Core / Service
Module:   app.core.suppliers.services
Purpose:  Business logic for supplier matching waterfall (exact → TF-IDF/embedding
          ≥ 0.9 auto-link → 0.3–0.9 HITL → <0.3 HITL "create new?"),
          delivery event recording + automatic score recomputation,
          reorder signal (stock below threshold → PO draft → HITL),
          and supplier discovery via SearXNG web search.
Depends:  app.core.suppliers.models, app.ml.supplier_scorer.scorer,
          app.infra.db.repos.supplier_repo, app.infra.db.repos.delivery_event_repo,
          app.infra.db.repos.hitl_repo, app.infra.llm.openai
HITL:     supplier_match_review, supplier_outreach, purchase_order_send (reorder)
"""

from __future__ import annotations

import uuid
from datetime import date

import numpy as np
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.suppliers.models import (
    DeliveryEventInput,
    DiscoveryCandidate,
    SupplierMatchResult,
)
from app.infra.db.models.delivery_event import SupplierDeliveryEvent
from app.infra.db.repos.delivery_event_repo import DeliveryEventRepository
from app.infra.db.repos.hitl_repo import HITLRepository
from app.infra.db.repos.product_repo import ProductRepository
from app.infra.db.repos.supplier_repo import SupplierRepository
from app.ml.supplier_scorer.scorer import ScorerResult, extract_features, score_supplier

logger = structlog.get_logger(__name__)


# ── TF-IDF helpers (pure — fully testable without DB) ────────────────────────


def _tfidf_match(
    query: str,
    candidates: list[tuple[str, str]],  # (supplier_id, name)
) -> tuple[str | None, float]:
    """
    Compute TF-IDF character n-gram cosine similarity between query and all candidates.
    Returns (best_id, score). Returns (None, 0.0) if no candidates.
    """
    if not candidates:
        return None, 0.0

    names = [c[1] for c in candidates]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    matrix = vectorizer.fit_transform(names + [query])
    query_vec = matrix[-1]
    sims = cosine_similarity(query_vec, matrix[:-1]).flatten()
    best_idx = int(sims.argmax())
    return candidates[best_idx][0], float(sims[best_idx])


def _cosine_sim(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


# ── Supplier matching waterfall ───────────────────────────────────────────────


async def match_supplier(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    embedding: list[float] | None = None,
) -> SupplierMatchResult:
    """
    Identify an existing supplier by name using the 5-step waterfall.

    1. Exact name match  → confidence 1.0, auto-link
    2. TF-IDF ≥ 0.9      → auto-link
    3. Embedding ≥ 0.9   → auto-link (if embedding provided)
    4. TF-IDF/emb 0.3–0.9 → HITL supplier_match_review
    5. All < 0.3 or empty → HITL "create new supplier?"
    """
    repo = SupplierRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)

    exact = await repo.find_by_name_exact(name)
    if exact:
        logger.info("supplier_match_exact", tenant_id=tenant_id, supplier_id=exact.supplier_id)
        return SupplierMatchResult(
            match_type="exact", supplier_id=exact.supplier_id, confidence=1.0
        )

    all_suppliers = await repo.list_all()
    candidates = [(s.supplier_id, s.name) for s in all_suppliers]

    tfidf_id, tfidf_score = _tfidf_match(name, candidates)

    emb_id: str | None = None
    emb_score = 0.0
    if embedding:
        emb_suppliers = await repo.list_with_embeddings()
        for sup in emb_suppliers:
            if sup.embedding:
                sim = _cosine_sim(embedding, list(sup.embedding))
                if sim > emb_score:
                    emb_score = sim
                    emb_id = sup.supplier_id

    best_score = max(tfidf_score, emb_score)
    best_id = emb_id if emb_score > tfidf_score else tfidf_id

    if best_score >= 0.9 and best_id:
        method = "embedding" if emb_score > tfidf_score else "tfidf"
        logger.info(
            "supplier_match_auto", tenant_id=tenant_id, method=method, score=best_score
        )
        return SupplierMatchResult(
            match_type=method, supplier_id=best_id, confidence=best_score
        )

    action_id = str(uuid.uuid4())
    payload: dict[str, object] = {"query_name": name, "confidence": round(best_score, 4)}
    if best_score >= 0.3 and best_id:
        candidate_name = next(
            (s.name for s in all_suppliers if s.supplier_id == best_id), ""
        )
        payload["candidate_supplier_id"] = best_id
        payload["candidate_name"] = candidate_name
        payload["action"] = "review_match"
    else:
        payload["action"] = "create_new"

    await hitl_repo.create(
        action_id=action_id,
        action_type="supplier_match_review",
        payload=payload,
    )
    logger.info(
        "supplier_match_hitl",
        tenant_id=tenant_id,
        action_id=action_id,
        score=best_score,
    )
    return SupplierMatchResult(
        match_type="hitl",
        supplier_id=None,
        confidence=best_score,
        hitl_action_id=action_id,
    )


# ── Delivery event + scoring ──────────────────────────────────────────────────


async def record_delivery_event(
    session: AsyncSession,
    tenant_id: str,
    supplier_id: str,
    event_in: DeliveryEventInput,
) -> ScorerResult:
    """
    Record one delivery performance event then immediately recompute the supplier score.
    Called by POST /suppliers/{id}/delivery-event.
    """
    repo = SupplierRepository(session, tenant_id)
    event_repo = DeliveryEventRepository(session, tenant_id)

    supplier = await repo.get_by_id(supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {supplier_id} not found")

    delivered = (
        date.fromisoformat(event_in.delivered_date) if event_in.delivered_date else None
    )
    event = SupplierDeliveryEvent(
        delivery_event_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        order_id=event_in.order_id,
        promised_date=date.fromisoformat(event_in.promised_date),
        delivered_date=delivered,
        items_ordered=event_in.items_ordered,
        items_received=event_in.items_received,
        items_damaged=event_in.items_damaged,
        price_agreed=event_in.price_agreed,
        price_billed=event_in.price_billed,
        response_time_hours=event_in.response_time_hours,
        notes=event_in.notes,
    )
    await event_repo.create(event)

    return await _recompute_score(session, tenant_id, supplier_id, repo, event_repo)


async def get_supplier_score(
    session: AsyncSession,
    tenant_id: str,
    supplier_id: str,
) -> ScorerResult:
    """Return current score without recording a new event."""
    repo = SupplierRepository(session, tenant_id)
    event_repo = DeliveryEventRepository(session, tenant_id)
    return await _recompute_score(session, tenant_id, supplier_id, repo, event_repo)


async def _recompute_score(
    session: AsyncSession,
    tenant_id: str,
    supplier_id: str,
    repo: SupplierRepository,
    event_repo: DeliveryEventRepository,
) -> ScorerResult:
    supplier = await repo.get_by_id(supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {supplier_id} not found")
    events = await event_repo.list_by_supplier(supplier_id)
    features = extract_features(events, supplier.email, supplier.phone)
    result = score_supplier(features, sample_count=len(events))
    await repo.set_score(supplier_id, result.score)
    logger.info(
        "supplier_score_updated",
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        score=result.score,
        method=result.method,
    )
    return result


# ── Reorder signal ────────────────────────────────────────────────────────────


async def trigger_reorder_check(
    session: AsyncSession,
    tenant_id: str,
) -> list[str]:
    """
    Find products below reorder_threshold → draft PO via GPT-4o → create HITL.
    Guard: skip product if a pending purchase_order_send HITL already exists for it.
    Returns list of created action_ids.
    """
    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    product_repo = ProductRepository(session, tenant_id)
    supplier_repo = SupplierRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)

    products = await product_repo.list_reorder_needed()
    if not products:
        return []

    best_supplier = await supplier_repo.get_best_scored()
    if best_supplier is None:
        all_suppliers = await supplier_repo.list_all()
        if not all_suppliers:
            logger.warning("reorder_check_no_suppliers", tenant_id=tenant_id)
            return []
        best_supplier = all_suppliers[0]

    action_ids: list[str] = []
    for product in products:
        pending = await hitl_repo.list_pending(action_type="purchase_order_send")
        if any(
            str(h.payload.get("product_id", "")) == product.product_id
            for h in pending
        ):
            logger.info(
                "reorder_check_skip_active_po",
                tenant_id=tenant_id,
                product_id=product.product_id,
            )
            continue

        reorder_qty = max(1, (product.reorder_threshold or 1) * 2)
        lang = best_supplier.language or "en"

        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": (
                    f"You are a procurement assistant drafting a purchase order email "
                    f"in {lang}. Be professional and concise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Draft a reorder email to supplier '{best_supplier.name}' "
                    f"requesting {reorder_qty} units of '{product.product_name}'. "
                    f"Current stock: {product.qty_in_stock}. "
                    f"Include: product name, quantity, company name placeholder [COMPANY], "
                    f"polite request for delivery timeline confirmation."
                ),
            },
        ]
        draft = await chat_completion(messages, model="gpt-4o", temperature=0.3)

        action_id = str(uuid.uuid4())
        await hitl_repo.create(
            action_id=action_id,
            action_type="purchase_order_send",
            payload={
                "product_id": product.product_id,
                "product_name": product.product_name,
                "supplier_id": best_supplier.supplier_id,
                "supplier_name": best_supplier.name,
                "to": best_supplier.email or "",
                "subject": f"Purchase Order — {product.product_name}",
                "body": draft,
                "reorder_qty": reorder_qty,
                "current_stock": product.qty_in_stock,
            },
        )
        action_ids.append(action_id)
        logger.info(
            "reorder_hitl_created",
            tenant_id=tenant_id,
            product_id=product.product_id,
            action_id=action_id,
        )

    return action_ids


# ── Supplier discovery ────────────────────────────────────────────────────────


async def discover_suppliers(
    session: AsyncSession,
    tenant_id: str,
    product_name: str,
    category: str,
    searxng_url: str,
) -> list[str]:
    """
    Search SearXNG for potential suppliers, draft outreach for top 3 candidates,
    create a HITL supplier_outreach action for each.
    Returns list of action_ids.
    """
    import httpx  # noqa: PLC0415

    from app.infra.llm.openai import chat_completion  # noqa: PLC0415

    hitl_repo = HITLRepository(session, tenant_id)
    query = f"{product_name} {category} wholesale supplier distributor"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{searxng_url}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            resp.raise_for_status()
            data: dict[str, object] = resp.json()
    except Exception as exc:
        logger.warning("supplier_discovery_search_failed", error=str(exc))
        return []

    raw = data.get("results", [])
    results = list(raw if isinstance(raw, list) else [])[:6]
    candidates: list[DiscoveryCandidate] = []
    for r in results:
        if isinstance(r, dict):
            candidates.append(DiscoveryCandidate(
                name=str(r.get("title", "Unknown"))[:80],
                website=str(r.get("url", "")) or None,
                snippet=str(r.get("content", ""))[:200] or None,
            ))

    action_ids: list[str] = []
    for candidate in candidates[:3]:
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": "You are a procurement assistant drafting a supplier outreach email.",
            },
            {
                "role": "user",
                "content": (
                    f"Draft a professional outreach email to '{candidate.name}' "
                    f"enquiring about their capacity to supply '{product_name}' ({category}). "
                    f"Include: introduction as [COMPANY], product interest, "
                    f"request for catalog and pricing, invitation to discuss."
                ),
            },
        ]
        draft = await chat_completion(messages, model="gpt-4o", temperature=0.4)

        action_id = str(uuid.uuid4())
        await hitl_repo.create(
            action_id=action_id,
            action_type="supplier_outreach",
            payload={
                "candidate_name": candidate.name,
                "candidate_website": candidate.website,
                "product_name": product_name,
                "category": category,
                "to": "",
                "subject": f"Supplier Enquiry — {product_name}",
                "body": draft,
            },
        )
        action_ids.append(action_id)
        logger.info(
            "supplier_discovery_hitl_created",
            tenant_id=tenant_id,
            candidate=candidate.name,
            action_id=action_id,
        )

    return action_ids
