"""
Feature:  Customer Management
Layer:    Core / Service
Module:   app.core.customers.services
Purpose:  Business logic for customer match waterfall:
            1. Exact email (1.0)   → auto-link
            2. Exact phone (0.95)  → auto-link
            3. TF-IDF name ≥ 0.85  → auto-link
            4. TF-IDF name 0.3–0.85 → HITL customer_match_review
            5. < 0.3               → auto-create new customer record
          Also handles: segment assignment, payment history score rolling update,
          and bulk re-segmentation (called by the admin panel or a nightly job).
Depends:  app.core.customers.models, app.infra.db.repos.customer_repo,
          app.infra.db.repos.hitl_repo
HITL:     customer_match_review
"""

from __future__ import annotations

import uuid

import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.customers.models import CustomerMatchResult
from app.infra.db.models.customer import Customer
from app.infra.db.repos.customer_repo import CustomerRepository
from app.infra.db.repos.hitl_repo import HITLRepository

logger = structlog.get_logger(__name__)

# ── TF-IDF name match (pure — fully testable) ─────────────────────────────────


def _tfidf_name_match(
    query: str,
    candidates: list[tuple[str, str]],  # (customer_id, name)
) -> tuple[str | None, float]:
    """
    TF-IDF character n-gram cosine similarity for customer name deduplication.
    Returns (best_customer_id, similarity_score). Returns (None, 0.0) if no candidates.
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


# ── Payment history score ─────────────────────────────────────────────────────


def compute_new_payment_score(old_score: float, n: int, outcome: float) -> float:
    """
    Rolling average: new_score = (old_score * n + outcome) / (n + 1)
    outcome: 1.0 = on time, 0.5 = late but before dunning, 0.0 = after dunning
    n: number of prior payments (0 for first payment).
    """
    new_n = n + 1
    return float(max(0.0, min(1.0, (old_score * n + outcome) / new_n)))


# ── Customer matching waterfall ───────────────────────────────────────────────


async def match_or_create_customer(
    session: AsyncSession,
    tenant_id: str,
    name: str,
    email: str | None,
    phone: str | None,
    customer_type: str,
) -> CustomerMatchResult:
    """
    Identify or create a customer record using the 5-step waterfall.

    Returns CustomerMatchResult with the customer_id (or None while HITL pending).
    """
    repo = CustomerRepository(session, tenant_id)
    hitl_repo = HITLRepository(session, tenant_id)

    # Step 1: exact email
    if email:
        existing = await repo.get_by_email(email)
        if existing:
            logger.info("customer_match_email", tenant_id=tenant_id, customer_id=existing.customer_id)
            return CustomerMatchResult(
                match_type="email",
                customer_id=existing.customer_id,
                confidence=1.0,
            )

    # Step 2: exact phone
    if phone:
        existing = await repo.get_by_phone(phone)
        if existing:
            logger.info("customer_match_phone", tenant_id=tenant_id, customer_id=existing.customer_id)
            return CustomerMatchResult(
                match_type="phone",
                customer_id=existing.customer_id,
                confidence=0.95,
            )

    # Step 3 & 4: TF-IDF name match
    all_customers = await repo.list_all()
    candidates = [(c.customer_id, c.name) for c in all_customers]
    best_id, best_score = _tfidf_name_match(name, candidates)

    if best_score >= 0.85 and best_id:
        logger.info(
            "customer_match_name_tfidf",
            tenant_id=tenant_id,
            customer_id=best_id,
            score=best_score,
        )
        return CustomerMatchResult(
            match_type="name_tfidf",
            customer_id=best_id,
            confidence=best_score,
        )

    if best_score >= 0.3 and best_id:
        action_id = str(uuid.uuid4())
        candidate_name = next(
            (c.name for c in all_customers if c.customer_id == best_id), ""
        )
        await hitl_repo.create(
            action_id=action_id,
            action_type="customer_match_review",
            payload={
                "query_name": name,
                "query_email": email,
                "query_phone": phone,
                "candidate_customer_id": best_id,
                "candidate_name": candidate_name,
                "confidence": round(best_score, 4),
            },
        )
        logger.info(
            "customer_match_hitl",
            tenant_id=tenant_id,
            action_id=action_id,
            score=best_score,
        )
        return CustomerMatchResult(
            match_type="hitl",
            customer_id=None,
            confidence=best_score,
            hitl_action_id=action_id,
        )

    # Step 5: auto-create
    customer_id = str(uuid.uuid4())
    new_customer = Customer(
        customer_id=customer_id,
        tenant_id=tenant_id,
        name=name,
        customer_type=customer_type,
        email=email,
        phone=phone,
    )
    await repo.create(new_customer)
    logger.info("customer_created", tenant_id=tenant_id, customer_id=customer_id)
    return CustomerMatchResult(
        match_type="created",
        customer_id=customer_id,
        confidence=0.0,
        created=True,
    )


# ── Segment + payment score helpers ──────────────────────────────────────────


async def update_segment(
    session: AsyncSession,
    tenant_id: str,
    customer_id: str,
    segment: str,
) -> None:
    """Assign a segment manually. segment ∈ {VIP, Regular, At-Risk, Dormant}."""
    repo = CustomerRepository(session, tenant_id)
    await repo.update_segment(customer_id, segment)
    logger.info(
        "customer_segment_updated",
        tenant_id=tenant_id,
        customer_id=customer_id,
        segment=segment,
    )


async def record_payment_outcome(
    session: AsyncSession,
    tenant_id: str,
    customer_id: str,
    outcome: float,
) -> float:
    """
    Update rolling payment_history_score.
    outcome: 1.0 on time, 0.5 late before dunning, 0.0 after dunning.
    Returns new score.
    """
    repo = CustomerRepository(session, tenant_id)
    customer = await repo.get_by_id(customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")

    n = customer.previous_dunning_count
    old_score = float(customer.payment_history_score)
    new_score = compute_new_payment_score(old_score, n, outcome)
    await repo.update_payment_history_score(customer_id, new_score)
    logger.info(
        "customer_payment_score_updated",
        tenant_id=tenant_id,
        customer_id=customer_id,
        old_score=old_score,
        new_score=new_score,
    )
    return new_score
